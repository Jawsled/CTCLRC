import sys
import traceback
import re
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtCore import QObject, QThread, Signal, Slot, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QDialogButtonBox

from ui import MainWindow, apply_dark_grey_theme
from align import generate_lrc, load_alignment_bundle, detect_existing_lrc, extract_embedded_lyrics, load_lyrics_text, has_lyrics_source, get_device_info, DEVICE


def resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parent / relative_path


@dataclass
class GenerateJob:
    audio: str
    lyrics_file: str | None = None
    lyrics_text: str | None = None
    output_path: str | None = None


class GenerateWorker(QObject):
    progress = Signal(int)
    message = Signal(str)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, jobs, language, lead_in, line_mode, word_mode, keep_sections):
        super().__init__()
        self.jobs = jobs
        self.language = language
        self.lead_in = lead_in
        self.line_mode = line_mode
        self.word_mode = word_mode
        self.keep_sections = keep_sections

    @Slot()
    def run(self):
        try:
            if not self.jobs:
                raise ValueError("No jobs to process.")

            self.message.emit(f"Loading alignment model [{DEVICE}]...")
            self.progress.emit(2)
            bundle = load_alignment_bundle()
            self.progress.emit(15)
            total = len(self.jobs)

            succeeded = 0
            skipped: list[str] = []
            failed: list[str] = []

            for index, job in enumerate(self.jobs):
                audio = job.audio
                self.message.emit(f"[{index + 1}/{total}] {Path(audio).name}")

                # Skip tracks with no lyrics source instead of aborting the batch
                try:
                    has_src, src_desc = has_lyrics_source(audio, job.lyrics_file, job.lyrics_text)
                except Exception:
                    has_src, src_desc = False, "lyrics check failed"
                if not has_src:
                    msg = f"[Skip] {Path(audio).name}: {src_desc}."
                    self.message.emit(msg)
                    skipped.append(f"{Path(audio).name} ({src_desc})")
                    continue

                def emit_progress(local_pct, _index=index):
                    overall = int(((_index + max(0, min(100, int(local_pct))) / 100.0) / total) * 100)
                    self.progress.emit(max(0, min(100, overall)))

                try:
                    generate_lrc(
                        audio,
                        job.lyrics_file,
                        job.lyrics_text,
                        model=bundle,
                        language=self.language,
                        lead_in=self.lead_in,
                        line_mode=self.line_mode,
                        word_mode=self.word_mode,
                        output_path=job.output_path,
                        progress_callback=emit_progress,
                        keep_sections=self.keep_sections,
                    )
                    succeeded += 1
                except FileNotFoundError as exc:
                    # Lyrics vanished between check and generation: skip, keep going
                    msg = f"[Skip] {Path(audio).name}: {exc}."
                    self.message.emit(msg)
                    skipped.append(f"{Path(audio).name} ({exc})")
                except ValueError as exc:
                    # Empty/unusable lyrics: skip, keep going
                    msg = f"[Skip] {Path(audio).name}: {exc}."
                    self.message.emit(msg)
                    skipped.append(f"{Path(audio).name} ({exc})")
                except Exception:
                    self.message.emit(f"[Error] {Path(audio).name} failed, continuing with next track.")
                    failed.append(f"{Path(audio).name}:\n{traceback.format_exc()}")

            summary = f"Done: {succeeded} generated, {len(skipped)} skipped, {len(failed)} failed (of {total})."
            self.message.emit(summary)
            for name in skipped:
                self.message.emit(f"  skipped: {name}")
            self.progress.emit(100)
            if succeeded == 0 and (skipped or failed):
                details = "\n".join(skipped + [f.split(':\n')[0] for f in failed])
                self.failed.emit(f"No tracks could be generated.\n{summary}\n{details}")
            elif failed:
                # Some succeeded: finish (errors already logged per track)
                self.finished.emit()
            else:
                self.finished.emit()
        except Exception:
            self.failed.emit(traceback.format_exc())


class LrclibPublishWorker(QObject):
    message = Signal(str)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs  # list of GenerateJob that were generated

    @Slot()
    def run(self):
        try:
            from lrclib_client import get_track_metadata, publish_lyrics
            for job in self.jobs:
                audio = job.audio
                # locate generated LRC file
                base = Path(job.output_path).with_suffix("") if job.output_path else Path(audio).with_suffix("")
                lrc_path = str(base) + ".lrc"
                if not Path(lrc_path).exists():
                    # fallback word lrc?
                    alt = str(base) + "_word.lrc"
                    if Path(alt).exists():
                        lrc_path = alt
                    else:
                        self.message.emit(f"[LRCLIB] LRC not found for {Path(audio).name}, skip publish.")
                        continue
                try:
                    synced = Path(lrc_path).read_text(encoding="utf-8")
                except Exception as e:
                    self.message.emit(f"[LRCLIB] Failed to read {lrc_path}: {e}")
                    continue
                # plain = strip timestamps
                plain_lines = []
                for line in synced.splitlines():
                    # remove [mm:ss.xx] prefixes
                    txt = re.sub(r"\[\d+:\d+(?:\.\d+)?\]", "", line).strip()
                    if txt:
                        plain_lines.append(txt)
                plain = "\n".join(plain_lines)
                meta = get_track_metadata(audio)
                # auto-complete metadata from file; if duration 0, try still publish with 0?
                if not meta["duration"] or meta["duration"] < 5:
                    # try to read actual LRC? keep 0 but LRCLIB requires duration >0
                    self.message.emit(f"[LRCLIB] Duration missing for {Path(audio).name}, skip publish.")
                    continue
                self.message.emit(f"[LRCLIB] Publishing {meta['trackName']} - {meta['artistName']} ...")
                # Bridge stage/solve progress into the log (throttle ticker chatter)
                _last_stage = [""]
                def _bridge(value, rate=0):
                    if isinstance(value, str):
                        if value != _last_stage[0]:
                            _last_stage[0] = value
                            self.message.emit(f"[LRCLIB] {value}")
                    elif isinstance(value, int) and value % 2000000 == 0:
                        self.message.emit(f"[LRCLIB] Solving… {value:,} hashes")
                ok, msg = publish_lyrics(
                    trackName=meta["trackName"],
                    artistName=meta["artistName"],
                    albumName=meta["albumName"],
                    duration=meta["duration"],
                    plainLyrics=plain,
                    syncedLyrics=synced,
                    progress_cb=_bridge,
                )
                if ok:
                    self.message.emit(f"[LRCLIB] Published: {Path(audio).name} -> {msg}")
                else:
                    self.message.emit(f"[LRCLIB] Failed {Path(audio).name}: {msg}")
            try:
                from lrclib_client import get_publish_debug_path
                self.message.emit(f"[LRCLIB] Stage log: {get_publish_debug_path()}")
            except Exception:
                pass
            self.finished.emit()
        except Exception:
            self.failed.emit(traceback.format_exc())


class App(QObject):
    def __init__(self):
        super().__init__()
        self.window = MainWindow()
        try:
            self.device_info = get_device_info()
        except Exception:
            self.device_info = {"device": DEVICE, "label": DEVICE.upper(), "detail": "", "torch_version": ""}
        self.window.set_device_info(self.device_info)
        print(f"Compute device: {self.device_info.get('label')} ({self.device_info.get('detail')})")
        self.window.batch_generate_button.clicked.connect(self.start_generate)
        self.thread = None
        self.worker = None
        self._publish_thread = None
        self._publish_worker = None
        self._pending_publish_jobs = []

    def _language_code(self) -> str:
        return self.window.language_combo.currentData() or "jpn"

    def _set_generate_enabled(self, enabled: bool):
        self.window.batch_generate_button.setEnabled(enabled)

    def _build_jobs(self):
        jobs = []
        for job in self.window.collect_batch_jobs():
            jobs.append(
                GenerateJob(
                    audio=job["audio"],
                    lyrics_file=job["lyrics_file"],
                    lyrics_text=job["lyrics_text"],
                    output_path=job["output_path"],
                )
            )
        return jobs

    def _check_existing_lrc(self, jobs) -> list[tuple[str, str]]:
        """Return list of (audio_path, existing_lrc_path) for tracks that have an LRC."""
        results = []
        for job in jobs:
            has_lrc, lrc_path = detect_existing_lrc(job.audio)
            if has_lrc and lrc_path:
                results.append((job.audio, lrc_path))
        return results

    def _prompt_export_existing(self, lrc_list: list[tuple[str, str]]) -> bool:
        """Show blocking dialog. Returns True = export all existing LRCs, False = skip all."""
        if not lrc_list:
            return False
        lines = [self.window.text("existing_lrc_found")]
        for audio_path, lrc_path in lrc_list:
            name = Path(audio_path).name
            lrc_name = Path(lrc_path).name
            lines.append(f"  {name} → {lrc_name}")
        count = len(lrc_list)
        msg_base = self.window.text("batch_existing_lrc_count").format(n=count)
        message = msg_base + "\n\n" + "\n".join(lines)
        dialog = QMessageBox(self.window)
        dialog.setWindowTitle("CTCLRC")
        dialog.setText(message)
        btn_export = dialog.addButton(self.window.text("export_existing"), QDialogButtonBox.ActionRole)
        btn_skip = dialog.addButton(self.window.text("skip_and_continue"), QDialogButtonBox.RejectRole)
        dialog.setDefaultButton(btn_skip)
        dialog.exec()
        return dialog.clickedButton() == btn_export

    def _export_existing_lrc(self, job: GenerateJob):
        """Copy the existing LRC to output dir with '_existing' suffix."""
        has_lrc, lrc_path = detect_existing_lrc(job.audio)
        if not has_lrc or not lrc_path:
            return
        base = Path(job.audio).stem
        out_dir = job.output_path and str(Path(job.output_path).parent) or str(Path(job.audio).parent)
        output_file = str(Path(out_dir) / (base + "_existing.lrc"))
        import shutil
        shutil.copy2(lrc_path, output_file)
        print(f"Exported existing LRC: {output_file}")

    # --------------------------------------------------------
    # LRCLIB: check before generating
    # --------------------------------------------------------
    def _check_lrclib_matches(self, jobs) -> list[tuple[GenerateJob, dict]]:
        """For each job, check LRCLIB. Returns list of (job, record) where synced exists."""
        matches = []
        try:
            from lrclib_client import check_lrclib_for_track
        except Exception as e:
            print(f"LRCLIB check skipped (import error): {e}")
            return matches
        for job in jobs:
            try:
                rec = check_lrclib_for_track(job.audio)
                if rec and rec.get("syncedLyrics"):
                    matches.append((job, rec))
                    self.window.append_log(self.window.text("lrclib_found").format(name=Path(job.audio).name))
                else:
                    self.window.append_log(self.window.text("lrclib_not_found").format(name=Path(job.audio).name))
            except Exception as e:
                self.window.append_log(f"[LRCLIB] check failed for {Path(job.audio).name}: {e}")
        return matches

    def _prompt_lrclib_matches(self, matches: list[tuple[GenerateJob, dict]]) -> str:
        """Show dialog for LRCLIB matches. Returns 'download'|'generate'|'skip'|'cancel'."""
        if not matches:
            return "generate"
        lines = []
        for job, rec in matches:
            lines.append(f"  {Path(job.audio).name} -> {rec.get('trackName')} / {rec.get('artistName')} (LRCLIB #{rec.get('id')})")
        msg = self.window.text("lrclib_use_existing") + "\n\n" + "\n".join(lines)
        dlg = QMessageBox(self.window)
        dlg.setWindowTitle("LRCLIB")
        dlg.setText(msg)
        btn_dl = dlg.addButton(self.window.text("download"), QDialogButtonBox.ActionRole)
        btn_gen = dlg.addButton(self.window.text("generate_anyway"), QDialogButtonBox.ActionRole)
        btn_skip = dlg.addButton(self.window.text("skip"), QDialogButtonBox.RejectRole)
        dlg.setDefaultButton(btn_dl)
        dlg.exec()
        clicked = dlg.clickedButton()
        if clicked == btn_dl:
            return "download"
        elif clicked == btn_gen:
            return "generate"
        elif clicked == btn_skip:
            return "skip"
        return "cancel"

    def _download_lrclib_for_jobs(self, matches: list[tuple[GenerateJob, dict]]) -> list[str]:
        from lrclib_client import download_synced_lrc
        created = []
        for job, rec in matches:
            base = Path(job.output_path).with_suffix("") if job.output_path else Path(job.audio).with_suffix("")
            # ensure output dir exists
            dest_path = Path(str(base) + ".lrc")
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest = str(dest_path)
            ok = download_synced_lrc(rec, dest)
            if ok and dest_path.exists():
                self.window.append_log(f"[LRCLIB] Downloaded -> {dest}")
                created.append(dest)
            else:
                self.window.append_log(f"[LRCLIB] Download failed for {Path(job.audio).name}")
        return created

    def _embed_lrc_into_audio(self, audio_path: str, lrc_path: str) -> None:
        try:
            from embed_lyrics import embed_synced_lyrics
            if not Path(lrc_path).exists():
                self.window.append_log(f"[Embed] LRC not found {lrc_path}, skip embed for {Path(audio_path).name}")
                return
            synced = Path(lrc_path).read_text(encoding="utf-8")
            ok, msg = embed_synced_lyrics(audio_path, synced)
            if ok:
                self.window.append_log(f"[Embed] {msg}")
            else:
                self.window.append_log(f"[Embed] Failed {Path(audio_path).name}: {msg}")
        except Exception as e:
            self.window.append_log(f"[Embed] Error for {Path(audio_path).name}: {e}")

    def _validate_jobs(self, jobs):
        """Validate jobs without aborting the whole batch.

        - Jobs with a missing audio file are dropped (logged by the caller).
        - Jobs whose lyrics file is missing fall back to other lyrics
          sources (pasted text / .txt / embedded) instead of failing.
        Returns (valid_jobs, skipped_messages).
        """
        valid = []
        skipped = []
        for job in jobs:
            if not job.audio or not Path(job.audio).exists():
                skipped.append(f"Audio file was not found, skipped: {job.audio}")
                continue
            if job.lyrics_file and not Path(job.lyrics_file).exists():
                skipped.append(
                    f"Lyrics file was not found for {Path(job.audio).name}, "
                    f"will try other sources: {job.lyrics_file}"
                )
                job.lyrics_file = None
            if job.output_path:
                try:
                    out_dir = Path(job.output_path).parent
                    out_dir.mkdir(parents=True, exist_ok=True)
                except Exception as exc:
                    skipped.append(f"Cannot create output dir for {Path(job.audio).name}, skipped: {exc}")
                    continue
            valid.append(job)
        return valid, skipped

    def start_generate(self):
        try:
            jobs = self._build_jobs()
            jobs, validation_notes = self._validate_jobs(jobs)
        except Exception as exc:
            QMessageBox.warning(self.window, "Error", str(exc))
            return

        if not jobs:
            QMessageBox.warning(self.window, "Error", "No jobs to process.")
            return

        # Always start with a clean log and progress, so LRCLIB checks are visible and progress resets
        self.window.clear_log()
        self.window.set_progress(0)
        self.window.append_log("===== CTCLRC =====")
        for note in validation_notes:
            self.window.append_log(f"[Skip] {note}")

        # LRCLIB check before generating — automatically download if match found
        lrclib_matches: list[tuple[GenerateJob, dict]] = []
        downloaded_lrcs: list[str] = []
        if hasattr(self.window, "check_lrclib_checkbox") and self.window.check_lrclib_checkbox.isChecked():
            self.window.append_log("Checking LRCLIB before generating...")
            self.window.set_progress(5)
            QApplication.processEvents()
            lrclib_matches = self._check_lrclib_matches(jobs)
            if lrclib_matches:
                self.window.append_log(f"LRCLIB match found for {len(lrclib_matches)} track(s), downloading...")
                self.window.set_progress(10)
                QApplication.processEvents()
                downloaded_lrcs = self._download_lrclib_for_jobs(lrclib_matches)
                # Embed downloaded lyrics if requested
                if hasattr(self.window, "embed_checkbox") and self.window.embed_checkbox.isChecked() and downloaded_lrcs:
                    for dest in downloaded_lrcs:
                        for job, rec in lrclib_matches:
                            base = Path(job.output_path).with_suffix("") if job.output_path else Path(job.audio).with_suffix("")
                            expected = str(base) + ".lrc"
                            if dest == expected:
                                self._embed_lrc_into_audio(job.audio, dest)
                                break
                if downloaded_lrcs:
                    self.window.append_log(f"Downloaded {len(downloaded_lrcs)} LRC file(s) from LRCLIB.")
                    self.window.set_progress(100)
                    QApplication.processEvents()
                    # Only remove jobs that were successfully downloaded
                    downloaded_set = set(downloaded_lrcs)
                    successful_audios = set()
                    for job, rec in lrclib_matches:
                        base = Path(job.output_path).with_suffix("") if job.output_path else Path(job.audio).with_suffix("")
                        expected = str(base) + ".lrc"
                        if expected in downloaded_set:
                            successful_audios.add(job.audio)
                    jobs = [j for j in jobs if j.audio not in successful_audios]
                    if not jobs:
                        self.window.append_log("All tracks handled via LRCLIB. No generation needed.")
                        # keep progress at 100 and re-enable
                        self.window.set_progress(100)
                        QMessageBox.information(self.window, "LRCLIB", f"Lyrics downloaded from LRCLIB ({len(downloaded_lrcs)} file(s))." + ("\nEmbedded into audio." if self.window.embed_checkbox.isChecked() else ""))
                        return
                    else:
                        self.window.append_log(f"Downloaded {len(downloaded_lrcs)} file(s) from LRCLIB, {len(jobs)} remaining to generate.")
                        self.window.set_progress(0)
                        QApplication.processEvents()
                else:
                    self.window.append_log("LRCLIB download failed (no files written), proceeding to generate.")
                    self.window.set_progress(0)
            else:
                self.window.append_log("No LRCLIB matches. Proceeding to generate.")
                self.window.set_progress(0)

        # Existing LRC check - just print if .lrc already exists next to track
        lrc_list = self._check_existing_lrc(jobs)
        if lrc_list:
            for audio_path, lrc_path in lrc_list:
                self.window.append_log(f"[Info] LRC already exists for {Path(audio_path).name}: {lrc_path}")
            # Not skipping - generation will overwrite. If you prefer to skip existing, uncomment:
            # existing_audios = {a for a, _ in lrc_list}
            # jobs = [j for j in jobs if j.audio not in existing_audios]
            # if not jobs:
            #     self.window.append_log("All tracks already have LRC. Skipping generation.")
            #     self.window.set_progress(0)
            #     return

        language = self._language_code()
        lead_in = float(self.window.lead_in_spin.value())
        line_mode = self.window.line_checkbox.isChecked()
        word_mode = self.window.word_checkbox.isChecked()
        keep_sections = self.window.section_checkbox.isChecked()
        self.window.save_settings()

        # stash for post-generate actions
        self._pending_publish_jobs = list(jobs)
        self._pending_embed = bool(hasattr(self.window, "embed_checkbox") and self.window.embed_checkbox.isChecked())

        dev = getattr(self, "device_info", {}) or {}
        if dev:
            self.window.append_log(f"Device: {dev.get('label', DEVICE)} ({dev.get('detail', '')})".rstrip(" ()"))
        self.window.append_log(f"Jobs  : {len(jobs)}")
        self.window.append_log(f"Lang  : {language}")
        self.window.append_log(f"Lead  : {lead_in:.3f}s")
        self.window.append_log(f"Line  : {line_mode}")
        self.window.append_log(f"Chars : {word_mode}")
        self.window.append_log(f"Sec   : {keep_sections}")
        self.window.append_log(f"Embed : {self._pending_embed}")
        self.window.append_log("")

        for index, job in enumerate(jobs, start=1):
            self.window.append_log(f"{index}. {job.audio}")
            if job.lyrics_text:
                self.window.append_log("   lyrics: <pasted text>")
            elif job.lyrics_file:
                self.window.append_log(f"   lyrics: {Path(job.lyrics_file).name}")
            else:
                self.window.append_log(f"   lyrics: <auto .txt>")
            emb = extract_embedded_lyrics(job.audio)
            if emb and emb.strip():
                e_lines, _ = load_lyrics_text(emb, keep_sections=keep_sections)
                self.window.append_log(f"   lyrics: embedded plain-text ({len(e_lines)} lines)")
            if job.output_path:
                self.window.append_log(f"   out   : {job.output_path}")
        self.window.append_log("")

        self._set_generate_enabled(False)
        self.window.set_progress(1)
        QApplication.processEvents()

        self.thread = QThread()
        self.worker = GenerateWorker(
            jobs,
            language,
            lead_in,
            line_mode,
            word_mode,
            keep_sections,
        )
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.window.set_progress)
        self.worker.message.connect(self.window.append_log)
        self.worker.finished.connect(self.generate_finished)
        self.worker.failed.connect(self.generate_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.clear_worker_refs)
        self.thread.start()

    @Slot()
    def generate_finished(self):
        self.window.set_progress(100)
        self._set_generate_enabled(True)
        # Verify that LRC files were actually created
        created = []
        missing = []
        for job in getattr(self, "_pending_publish_jobs", []):
            base = Path(job.output_path).with_suffix("") if job.output_path else Path(job.audio).with_suffix("")
            lrc_path = str(base) + ".lrc"
            alt = str(base) + "_word.lrc"
            if Path(lrc_path).exists():
                created.append(lrc_path)
            elif Path(alt).exists():
                created.append(alt)
            else:
                missing.append(job.audio)
        if created:
            self.window.append_log(f"LRC generated: {len(created)} file(s).")
            for p in created:
                self.window.append_log(f"  -> {p}")
        if missing:
            self.window.append_log(f"WARNING: No LRC created for {len(missing)} track(s):")
            for a in missing:
                self.window.append_log(f"  - {Path(a).name}")

        # Embed synced lyrics if requested
        if getattr(self, "_pending_embed", False):
            for job in self._pending_publish_jobs:
                base = Path(job.output_path).with_suffix("") if job.output_path else Path(job.audio).with_suffix("")
                lrc_path = str(base) + ".lrc"
                if not Path(lrc_path).exists():
                    alt = str(base) + "_word.lrc"
                    if Path(alt).exists():
                        lrc_path = alt
                    else:
                        self.window.append_log(f"[Embed] No LRC for {Path(job.audio).name}, skip embed.")
                        continue
                self._embed_lrc_into_audio(job.audio, lrc_path)

        # Auto-upload to LRCLIB if requested; otherwise manual via Lyric Viewer
        upload_checked = bool(
            hasattr(self.window, "upload_lrclib_checkbox")
            and self.window.upload_lrclib_checkbox.isChecked()
        )
        if upload_checked and created:
            created_set = set(created)
            publish_jobs = []
            for job in self._pending_publish_jobs:
                base = Path(job.output_path).with_suffix("") if job.output_path else Path(job.audio).with_suffix("")
                if str(base) + ".lrc" in created_set or str(base) + "_word.lrc" in created_set:
                    publish_jobs.append(job)
            if publish_jobs:
                self.window.append_log(f"[LRCLIB] Auto-uploading {len(publish_jobs)} track(s)...")
                self._start_publish_worker(publish_jobs)
                return
        # LRCLIB publish is manual via Lyric Viewer (after verifying timings)
        QTimer.singleShot(0, lambda: QMessageBox.information(self.window, "Finished", "LRC file was generated.\nOpen Lyric Viewer to verify/edit and publish to LRCLIB manually if desired."))

    def _start_publish_worker(self, jobs):
        self.window.append_log("[LRCLIB] Starting publish (may take ~30s for PoW)...")
        self._publish_thread = QThread()
        self._publish_worker = LrclibPublishWorker(jobs)
        self._publish_worker.moveToThread(self._publish_thread)
        self._publish_thread.started.connect(self._publish_worker.run)
        self._publish_worker.message.connect(self.window.append_log)
        # NOTE: bound slots (queued to the GUI thread). Plain lambdas would run
        # IN the worker thread and touch widgets off-thread, freezing the app.
        self._publish_worker.finished.connect(self._on_publish_finished)
        self._publish_worker.failed.connect(self._on_publish_failed)
        self._publish_worker.finished.connect(self._publish_thread.quit)
        self._publish_worker.failed.connect(self._publish_thread.quit)
        self._publish_thread.finished.connect(self._publish_worker.deleteLater)
        self._publish_thread.finished.connect(self._publish_thread.deleteLater)
        self._publish_thread.finished.connect(self._clear_publish_refs)
        self._publish_thread.start()

    @Slot()
    def _on_publish_finished(self):
        # Runs in the GUI thread (queued connection from the worker thread)
        self.window.append_log("[LRCLIB] Publish finished.")
        QMessageBox.information(self.window, "LRCLIB", "Publish finished. See log for details.")

    @Slot(str)
    def _on_publish_failed(self, traceback_text):
        # Runs in the GUI thread (queued connection from the worker thread)
        QMessageBox.critical(self.window, "LRCLIB Error", traceback_text)

    @Slot()
    def _clear_publish_refs(self):
        self._publish_thread = None
        self._publish_worker = None

    @Slot(str)
    def generate_failed(self, traceback_text):
        print(traceback_text)
        self.window.set_progress(0)
        self.window.append_log("Generation failed. See error dialog.")
        self._set_generate_enabled(True)
        QTimer.singleShot(0, lambda: QMessageBox.critical(self.window, "Error", traceback_text))

    @Slot()
    def clear_worker_refs(self):
        self.thread = None
        self.worker = None


def main():
    app = QApplication(sys.argv)
    # Dark grey (dark mode) theme, applied app-wide regardless of OS setting
    try:
        apply_dark_grey_theme(app)
    except Exception:
        pass
    icon_path = resource_path("assets/ctclrc.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    controller = App()
    if icon_path.exists():
        controller.window.setWindowIcon(QIcon(str(icon_path)))
    controller.window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    # Required for ProcessPoolExecutor (LRCLIB PoW solver) in frozen Windows builds
    try:
        import multiprocessing
        multiprocessing.freeze_support()
    except Exception:
        pass
    main()
