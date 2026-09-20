"""LRCLIB API client: check before generate, upload after generate.
Uses only stdlib + mutagen for metadata extraction.
"""
import hashlib
import json
import os
import tempfile
import threading
import urllib.request
import urllib.parse
import urllib.error
import time
from pathlib import Path
from typing import Optional

LRCLIB_BASE = "https://lrclib.net"
USER_AGENT = "CTCLRC/1.0 (https://github.com/CTCLRC)"

# --------------------------------------------------------
# Metadata extraction
# --------------------------------------------------------
def get_audio_duration(audio_path: str) -> float | None:
    """Return duration in seconds, or None."""
    # Try mutagen first
    try:
        from mutagen import File as MutagenFile
        mf = MutagenFile(str(audio_path))
        if mf is not None and hasattr(mf, "info") and mf.info and hasattr(mf.info, "length"):
            if mf.info.length and mf.info.length > 0:
                return float(mf.info.length)
    except Exception:
        pass
    # Fallback: av
    try:
        import av
        with av.open(str(audio_path), metadata_errors="ignore") as cont:
            # estimate from stream duration
            if cont.duration is not None and cont.duration > 0:
                # av duration is in microseconds (time_base)
                return float(cont.duration) / 1_000_000
            # try decode a bit to guess? fallback read stream
            stream = cont.streams.audio[0] if cont.streams.audio else None
            if stream and stream.duration:
                tb = float(stream.time_base) if stream.time_base else 1/1000
                return float(stream.duration * tb)
    except Exception:
        pass
    return None


def get_track_metadata(audio_path: str) -> dict:
    """Extract trackName, artistName, albumName, duration from audio tags.
    Returns dict with keys: trackName, artistName, albumName, duration
    Missing values become empty string / 0.
    """
    path = Path(audio_path)
    track = path.stem
    artist = ""
    album = ""
    duration = get_audio_duration(str(path)) or 0.0

    ext = path.suffix.lower()
    try:
        from mutagen import File as MutagenFile
        mf = MutagenFile(str(path), easy=True)
        if mf is not None:
            # easy mode returns list values
            def _get(key):
                v = mf.get(key)
                if v and len(v) > 0:
                    return str(v[0]).strip()
                return ""
            # easy keys: title, artist, album
            t = _get("title")
            if t:
                track = t
            a = _get("artist")
            if a:
                artist = a
            al = _get("album")
            if al:
                album = al
    except Exception:
        pass

    # Non-easy fallback for some formats
    if not artist or not album:
        try:
            if ext == ".mp3":
                from mutagen.id3 import ID3
                tags = ID3(str(path))
                if not artist:
                    for key in ("TPE1", "TPE2"):
                        if key in tags:
                            artist = str(tags[key].text[0]) if tags[key].text else ""
                            if artist:
                                break
                if not track or track == path.stem:
                    if "TIT2" in tags and tags["TIT2"].text:
                        track = str(tags["TIT2"].text[0])
                if not album and "TALB" in tags and tags["TALB"].text:
                    album = str(tags["TALB"].text[0])
            elif ext in (".m4a", ".mp4"):
                from mutagen.mp4 import MP4
                tags = MP4(str(path))
                if not track or track == path.stem:
                    v = tags.get("\xa9nam")
                    if v:
                        track = str(v[0])
                if not artist:
                    v = tags.get("\xa9ART")
                    if v:
                        artist = str(v[0])
                if not album:
                    v = tags.get("\xa9alb")
                    if v:
                        album = str(v[0])
            elif ext in (".flac", ".ogg", ".opus"):
                # mutagen easy already handles, but try vorbis
                from mutagen.flac import FLAC
                from mutagen.oggvorbis import OggVorbis
                audio = None
                try:
                    if ext == ".flac":
                        audio = FLAC(str(path))
                    elif ext == ".ogg":
                        audio = OggVorbis(str(path))
                except Exception:
                    pass
                if audio is not None:
                    if not track or track == path.stem:
                        v = audio.get("TITLE") or audio.get("title")
                        if v:
                            track = str(v[0])
                    if not artist:
                        v = audio.get("ARTIST") or audio.get("artist")
                        if v:
                            artist = str(v[0])
                    if not album:
                        v = audio.get("ALBUM") or audio.get("album")
                        if v:
                            album = str(v[0])
        except Exception:
            pass

    return {
        "trackName": track.strip() or path.stem,
        "artistName": artist.strip(),
        "albumName": album.strip(),
        "duration": float(duration),
    }


# --------------------------------------------------------
# HTTP helpers (urllib, no extra dep)
# --------------------------------------------------------
def _http_get(url: str, params: dict | None = None, timeout: int = 12) -> tuple[int, dict | list | str | None]:
    if params:
        qs = urllib.parse.urlencode(params)
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            ctype = resp.headers.get("Content-Type", "")
            if "json" in ctype:
                return resp.status, json.loads(body)
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore") if e.fp else ""
        try:
            return e.code, json.loads(body) if body else None
        except Exception:
            return e.code, body
    except Exception as e:
        return 0, str(e)


def _http_post(url: str, json_body: dict | None = None, headers: dict | None = None, timeout: int = 15) -> tuple[int, dict | None]:
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        hdrs = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
    else:
        # No body (e.g. /api/request-challenge): send empty POST without a
        # JSON content-type, like the official clients do.
        data = None
        hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, method="POST", headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            try:
                return resp.status, json.loads(body) if body else None
            except Exception:
                return resp.status, {"raw": body}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore") if e.fp else ""
        try:
            return e.code, json.loads(body) if body else None
        except Exception:
            return e.code, {"raw": body, "error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}


# --------------------------------------------------------
# LRCLIB API
# --------------------------------------------------------
def lrclib_get(trackName: str, artistName: str, albumName: str, duration: float, cached: bool = True) -> dict | None:
    """Query GET /api/get (or /api/get-cached). Returns record dict or None if 404."""
    endpoint = "/api/get-cached" if cached else "/api/get"
    url = LRCLIB_BASE + endpoint
    params = {
        "track_name": trackName,
        "artist_name": artistName,
        "album_name": albumName,
        "duration": round(float(duration), 2),
    }
    status, data = _http_get(url, params=params)
    if status == 200 and isinstance(data, dict) and data.get("id"):
        return data
    # 404 is not found
    return None


def lrclib_search(trackName: str = "", artistName: str = "", albumName: str = "", q: str = "") -> list:
    """Search fallback."""
    url = LRCLIB_BASE + "/api/search"
    params = {}
    if q:
        params["q"] = q
    if trackName:
        params["track_name"] = trackName
    if artistName:
        params["artist_name"] = artistName
    if albumName:
        params["album_name"] = albumName
    if not params:
        return []
    status, data = _http_get(url, params=params)
    if status == 200 and isinstance(data, list):
        return data
    return []


def check_lrclib_for_track(audio_path: str, metadata: dict | None = None) -> dict | None:
    """Check LRCLIB for matching lyrics. Returns record or None."""
    if metadata is None:
        metadata = get_track_metadata(audio_path)
    dur = metadata.get("duration") or 0
    # If duration is 0, we can't reliably query /get; use search fallback
    if dur and dur > 5:
        rec = lrclib_get(metadata["trackName"], metadata["artistName"], metadata["albumName"], dur, cached=True)
        if rec and rec.get("syncedLyrics"):
            return rec
        # try without cache
        rec2 = lrclib_get(metadata["trackName"], metadata["artistName"], metadata["albumName"], dur, cached=False)
        if rec2 and rec2.get("syncedLyrics"):
            return rec2
    # search fallback: look for same track + artist
    results = lrclib_search(trackName=metadata["trackName"], artistName=metadata["artistName"])
    # pick best: duration within 5s and has synced
    best = None
    for r in results:
        if not r.get("syncedLyrics"):
            continue
        # simple title match (case-insensitive)
        if r.get("trackName", "").strip().lower() != metadata["trackName"].strip().lower():
            # allow fuzzy still? keep but score lower
            pass
        if dur and r.get("duration"):
            if abs(float(r["duration"]) - float(dur)) <= 5:
                best = r
                break
        elif not dur:
            best = r
            break
    return best


# --------------------------------------------------------
# Publish (PoW)
# --------------------------------------------------------
def _is_nonce_valid(prefix_bytes: bytes, nonce: int, target: bytes) -> bool:
    """Check sha256(prefix + str(nonce)) < target (bytes compare)."""
    h = hashlib.sha256(prefix_bytes + str(nonce).encode("ascii")).digest()
    return h < target


def _scan_nonce_chunk(args) -> int | None:
    """Scan [start, start+count) for a valid nonce. Module-level so it pickles
    for ProcessPoolExecutor workers. Returns the nonce or None."""
    prefix_bytes, target, start, count = args
    end = start + count
    nonce = start
    while nonce < end:
        h = hashlib.sha256(prefix_bytes + str(nonce).encode("ascii")).digest()
        if h < target:
            return nonce
        nonce += 1
    return None


def _solve_challenge(prefix: str, target_hex: str, cancel_check=None, progress_cb=None,
                     num_threads: int = 1) -> str | None:
    """Brute-force PoW: find nonce such that sha256(prefix+nonce) < target.
    Returns nonce as string, or None if cancelled.

    num_threads=1 (default) searches nonces ascending in-process and is
    deterministic (always finds the smallest valid nonce). num_threads>1
    scans nonce chunks across worker processes (real parallelism: the tight
    hashing loop is GIL-bound so threads don't scale) and returns the first
    valid nonce found. Any valid nonce is accepted by LRCLIB, so callers
    doing real publishes should use multiple workers.
    """
    target = bytes.fromhex(target_hex)
    prefix_bytes = prefix.encode("utf-8")
    if num_threads is None or num_threads < 1:
        num_threads = 1

    if num_threads == 1:
        nonce = 0
        start = time.time()
        last_report = 0.0
        while True:
            # Check for cancellation every 4096 iterations (cheap bitwise test)
            if (nonce & 0xFFF) == 0 and cancel_check and cancel_check():
                return None
            if _is_nonce_valid(prefix_bytes, nonce, target):
                return str(nonce)
            nonce += 1
            if progress_cb and nonce % 50000 == 0:
                now = time.time()
                if now - last_report > 0.5:
                    elapsed = now - start
                    rate = nonce / elapsed if elapsed > 0 else 0
                    try:
                        progress_cb(nonce, rate)
                    except Exception:
                        pass
                    last_report = now
        # unreachable

    # Multi-process: chunk the nonce space across workers for real speedup.
    import concurrent.futures as cf
    from concurrent.futures import ProcessPoolExecutor

    chunk = 100_000
    total = 0
    start = time.time()
    last_report = 0.0
    next_start = 0
    try:
        with ProcessPoolExecutor(max_workers=num_threads) as ex:
            pending: dict = {}
            for _ in range(num_threads * 2):
                fut = ex.submit(_scan_nonce_chunk, (prefix_bytes, target, next_start, chunk))
                pending[fut] = next_start
                next_start += chunk
            while pending:
                if cancel_check and cancel_check():
                    ex.shutdown(wait=False, cancel_futures=True)
                    return None
                done, _ = cf.wait(list(pending.keys()), timeout=0.2)
                for fut in done:
                    pending.pop(fut, None)
                    try:
                        hit = fut.result()
                    except Exception:
                        hit = None
                    if hit is not None:
                        ex.shutdown(wait=False, cancel_futures=True)
                        return str(hit)
                    total += chunk
                    if progress_cb:
                        now = time.time()
                        if now - last_report > 0.5:
                            last_report = now
                            rate = total / max(now - start, 1e-6)
                            try:
                                progress_cb(total, rate)
                            except Exception:
                                pass
                    fut2 = ex.submit(_scan_nonce_chunk, (prefix_bytes, target, next_start, chunk))
                    pending[fut2] = next_start
                    next_start += chunk
    except Exception:
        # Process spawn failed (restricted env): fall back to single-process
        # search so publish still works, just slower.
        return _solve_challenge(prefix, target_hex, cancel_check=cancel_check,
                                progress_cb=progress_cb, num_threads=1)
    return None


def request_challenge(timeout: int = 15) -> tuple[str, str] | None:
    """Request a fresh PoW challenge via POST /api/request-challenge.

    The endpoint takes no body (official clients send an empty POST), so we
    send exactly that: POST with no payload and no JSON content-type.
    Returns (prefix, target) or None on network/server error.
    """
    try:
        # Plain POST with empty body and only a User-Agent header, exactly
        # like fetch(url, {method: "POST"}) in the working reference clients.
        req = urllib.request.Request(
            LRCLIB_BASE + "/api/request-challenge",
            data=b"",
            method="POST",
            headers={"User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            status = resp.status
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="ignore") if e.fp else ""
        except Exception:
            body = ""
        status = e.code
    except Exception:
        return None
    if status not in (200, 201):
        return None
    try:
        data = json.loads(body) if body else None
    except Exception:
        return None
    if isinstance(data, dict) and "prefix" in data and "target" in data:
        try:
            # Validate target is hex so _solve_challenge won't crash later
            bytes.fromhex(data["target"])
        except Exception:
            return None
        return data["prefix"], data["target"]
    return None


def verify_publish_token(prefix: str, nonce: str | int, target_hex: str) -> tuple[bool, str]:
    """Locally verify a solved token before sending it.

    Recomputes sha256(prefix + str(nonce)) and checks it against the target,
    exactly like the server does. Returns (valid, hash_hex). This catches a
    bad token client-side instead of burning a publish attempt on it.
    """
    try:
        target = bytes.fromhex(target_hex)
    except Exception as e:
        return False, f"bad target hex: {e}"
    try:
        h = hashlib.sha256(f"{prefix}{nonce}".encode("utf-8")).digest()
    except Exception as e:
        return False, f"hash failed: {e}"
    return (h < target), h.hex()


def _emit_progress(progress_cb, value, rate=0) -> None:
    """Send a progress update. value is either (nonce, rate) numbers like the
    PoW solver emits, or a plain stage string ("Uploading…")."""
    if progress_cb is None:
        return
    try:
        progress_cb(value, rate)
    except Exception:
        pass


def get_publish_debug_path() -> str:
    """Path of the publish diagnostics log (temp dir, always writable)."""
    try:
        return os.path.join(tempfile.gettempdir(), "ctclrc_lrclib_debug.log")
    except Exception:
        return "ctclrc_lrclib_debug.log"


def _dbg(msg: str) -> None:
    """Append a timestamped line to the publish diagnostics log."""
    try:
        path = get_publish_debug_path()
        try:
            if os.path.getsize(path) > 200_000:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("(rotated)\n")
        except OSError:
            pass
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


def publish_lyrics(trackName: str, artistName: str, albumName: str, duration: float,
                   plainLyrics: str, syncedLyrics: str, timeout: int = 30,
                   cancel_check=None, progress_cb=None, num_threads: int | None = None,
                   max_attempts: int = 3, post_timeout: int = 25) -> tuple[bool, str]:
    """Publish to LRCLIB. Solves PoW automatically. Returns (success, message).

    Mirrors the working reference clients (lrclibuploader/lrclibup/LRCGET):
    plain-POST challenge, token "{prefix}:{nonce}", JSON body with integer
    duration. Each attempt uses a fresh challenge (tokens are single-use and
    expire after ~5 minutes). Retries with a fresh token on 400
    IncorrectPublishToken, transport timeouts and 5xx; 429 and other 4xx
    return immediately. Every stage (challenge/solve/verify/upload) emits
    progress so the UI never sits on a stale label.
    """
    # API docs mark trackName, artistName, albumName and duration required.
    if not (trackName or "").strip():
        return False, "Missing track name: cannot publish without a title."
    if not (artistName or "").strip():
        return False, ("Missing artist name: LRCLIB requires artistName. "
                        "Tag the audio file first, then retry.")
    try:
        dur = int(round(float(duration)))
    except (TypeError, ValueError):
        dur = 0
    if not 1 <= dur <= 3600:
        return False, f"Invalid duration ({duration!r}): LRCLIB needs 1-3600 seconds."
    if not (plainLyrics or "").strip() and not (syncedLyrics or "").strip():
        return False, "No lyrics to publish (both plain and synced are empty)."
    threads = num_threads if num_threads else (os.cpu_count() or 4)
    body = {
        "trackName": trackName,
        "artistName": artistName,
        "albumName": albumName or "",
        "duration": dur,
        "plainLyrics": plainLyrics or "",
        "syncedLyrics": syncedLyrics or "",
    }

    last_err = ""
    for attempt in range(1, max(1, max_attempts) + 1):
        if cancel_check and cancel_check():
            return False, "Cancelled."
        _emit_progress(progress_cb, f"Requesting challenge (attempt {attempt})…")
        _dbg(f"attempt {attempt}: start track={trackName!r} artist={artistName!r}")
        chall = request_challenge()
        if not chall:
            last_err = (f"Attempt {attempt}: failed to get challenge from LRCLIB "
                        "(network or server error).")
            _dbg(f"attempt {attempt}: no challenge received")
            continue
        _dbg(f"attempt {attempt}: challenge prefix={chall[0][:8]}...")
        if cancel_check and cancel_check():
            return False, "Cancelled before solving PoW."
        prefix, target = chall
        _emit_progress(progress_cb, "Solving proof-of-work…")
        t0 = time.time()
        nonce = _solve_challenge(prefix, target, cancel_check=cancel_check,
                                 progress_cb=progress_cb, num_threads=threads)
        solve_dt = time.time() - t0
        if nonce is None:
            _dbg(f"attempt {attempt}: cancelled during PoW")
            return False, "Cancelled during proof-of-work."
        # Self-verify the token exactly like the server does before sending.
        _emit_progress(progress_cb, "Verifying token…")
        valid, hash_hex = verify_publish_token(prefix, nonce, target)
        _dbg(f"attempt {attempt}: solved nonce={nonce} in {solve_dt:.1f}s "
             f"hash={hash_hex[:16]}... valid={valid}")
        if not valid:
            last_err = (f"Attempt {attempt}: solver produced an invalid token "
                        f"(prefix={prefix[:8]}... nonce={nonce} hash={hash_hex[:16]}... "
                        f"target={target[:16]}..., solved in {solve_dt:.1f}s). "
                        f"Retrying with a fresh challenge.")
            continue
        token = f"{prefix}:{nonce}"
        headers = {"X-Publish-Token": token}
        # Upload with a live ticker so a slow server never looks frozen, plus
        # a watchdog: per-op socket timeouts can't catch a server that stalls
        # mid-response, so cap the whole POST and stay cancel-aware.
        _emit_progress(progress_cb, "Uploading to LRCLIB…")
        _dbg(f"attempt {attempt}: POST start token={prefix[:8]}...:{nonce} "
             f"track={trackName!r} artist={artistName!r} duration={dur}")
        stop_ticker = threading.Event()
        def _ticker(stop=stop_ticker, cb=progress_cb):
            t_start = time.time()
            while not stop.wait(2):
                el = time.time() - t_start
                _emit_progress(cb, f"Uploading to LRCLIB… ({el:.0f}s)")
        ticker = threading.Thread(target=_ticker, daemon=True)
        ticker.start()
        post_box: dict = {}
        def _do_post(box=post_box):
            try:
                box["res"] = _http_post(LRCLIB_BASE + "/api/publish", json_body=body,
                                        headers=headers, timeout=post_timeout)
            except Exception as e:  # _http_post already swallows these; last resort
                box["exc"] = e
        post_thread = threading.Thread(target=_do_post, daemon=True)
        t1 = time.time()
        post_thread.start()
        overall_deadline = t1 + 120
        hung = False
        while post_thread.is_alive():
            if cancel_check and cancel_check():
                stop_ticker.set()
                _dbg(f"attempt {attempt}: cancelled during upload")
                return False, "Cancelled during upload."
            post_thread.join(timeout=0.5)
            if time.time() > overall_deadline:
                hung = True
                break
        stop_ticker.set()
        ticker.join(timeout=3)
        post_dt = time.time() - t1
        if hung:
            _dbg(f"attempt {attempt}: POST hung beyond 120s overall deadline, abandoning")
            last_err = (f"Attempt {attempt}: upload stalled (no response within 120s, "
                        f"solve={solve_dt:.1f}s).")
            if attempt < max(1, max_attempts):
                last_err += " Retrying with a fresh challenge."
            continue
        if "exc" in post_box:
            _dbg(f"attempt {attempt}: POST raised {post_box['exc']!r}")
            last_err = f"Attempt {attempt}: upload error: {post_box['exc']}"
            continue
        status, data = post_box.get("res", (0, {"error": "no response"}))
        _dbg(f"attempt {attempt}: POST done status={status} in {post_dt:.1f}s")
        if status in (200, 201):
            # 201 Created means the lyrics are stored, even when the server
            # returns an empty body (data is None). That is still success.
            _dbg(f"attempt {attempt}: PUBLISHED track={trackName!r}")
            detail = data if data is not None else "created (empty response body)"
            return True, f"Published (status {status}): {detail}"
        if isinstance(data, dict):
            err = data.get("message") or data.get("error") or str(data)
        else:
            err = str(data)
        last_err = (f"Attempt {attempt}: HTTP {status} "
                    f"(token={prefix[:8]}...:{nonce}, hash={hash_hex[:16]}..., "
                    f"solve={solve_dt:.1f}s, upload={post_dt:.1f}s): {err}")
        if status == 429:
            return False, f"Rate limited (HTTP 429): {err} (wait a bit and retry)"
        if status == 0 or status == 400 or 500 <= status < 600:
            # Transport timeout, consumed/expired token, or transient server
            # error: retry with a fresh challenge.
            continue
        # Other 4xx (validation etc.): retrying won't help.
        return False, last_err
    return False, last_err or "Publish failed for unknown reasons."


def download_synced_lrc(record: dict, dest_path: str) -> bool:
    """Save LRCLIB record's syncedLyrics to dest_path."""
    synced = record.get("syncedLyrics") or ""
    if not synced.strip():
        return False
    Path(dest_path).write_text(synced, encoding="utf-8")
    return True
