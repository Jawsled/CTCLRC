from pathlib import Path
from dataclasses import dataclass

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus"}
LYRIC_EXTS = [".lrc", ".txt"]  # priority

@dataclass
class ScanResult:
    audio_path: str
    lyric_path: str | None
    lrc_exists: bool
    status: str  # "matched", "missing", "existing_lrc"

def scan_directory(root: Path | str, recursive: bool = True) -> list[ScanResult]:
    root = Path(root)
    if not root.is_dir():
        return []
    # Find all audio files
    audio_files: list[Path] = []
    if recursive:
        for ext in AUDIO_EXTS:
            audio_files.extend(root.rglob(f"*{ext}"))
            # Also handle uppercase
            audio_files.extend(root.rglob(f"*{ext.upper()}"))
    else:
        for ext in AUDIO_EXTS:
            audio_files.extend(root.glob(f"*{ext}"))
            audio_files.extend(root.glob(f"*{ext.upper()}"))
    # Dedupe (rglob with both cases may duplicate on case-insensitive FS)
    seen = set()
    uniq: list[Path] = []
    for p in audio_files:
        rp = str(p.resolve()).lower()
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    uniq.sort(key=lambda p: str(p).lower())

    results: list[ScanResult] = []
    for audio in uniq:
        # Check for existing .lrc next to track (same name)
        lrc_cand = audio.with_suffix(".lrc")
        word_cand = audio.with_name(audio.stem + "_word.lrc")
        txt_cand = audio.with_suffix(".txt")
        lyric_path: str | None = None
        lrc_exists = False
        status = "missing"
        if lrc_cand.exists():
            lyric_path = str(lrc_cand.resolve())
            lrc_exists = True
            status = "existing_lrc"
        elif word_cand.exists():
            lyric_path = str(word_cand.resolve())
            lrc_exists = True
            status = "existing_lrc"
        else:
            # Look for matching lyric by stem in same dir
            # Priority: .lrc > .txt
            for ext in LYRIC_EXTS:
                cand = audio.with_suffix(ext)
                if cand.exists():
                    lyric_path = str(cand.resolve())
                    status = "matched" if ext == ".lrc" else "matched_txt"
                    break
        results.append(ScanResult(
            audio_path=str(audio.resolve()),
            lyric_path=lyric_path,
            lrc_exists=lrc_exists,
            status=status,
        ))
    return results

def format_counter(results: list[ScanResult]) -> str:
    total = len(results)
    with_lyric = sum(1 for r in results if r.lyric_path and not r.lrc_exists)
    existing = sum(1 for r in results if r.lrc_exists)
    missing = total - with_lyric - existing
    return f"Tracks: {total}  •  With lyrics: {with_lyric}  •  Existing .lrc: {existing}  •  Missing: {missing}"
