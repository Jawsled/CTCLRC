"""Embed synced lyrics into audio files.
Supports MP3 (SYLT/USLT), FLAC/OGG (SYNCEDLYRICS/LYRICS), M4A (lyrics).
"""
from pathlib import Path


def embed_synced_lyrics(audio_path: str, synced_lrc: str, plain_lyrics: str | None = None) -> tuple[bool, str]:
    """Embed synced LRC text into audio file metadata.
    Returns (success, message). Overwrites existing lyrics tags.
    """
    p = Path(audio_path)
    if not p.exists():
        return False, f"File not found: {audio_path}"
    ext = p.suffix.lower()
    lrc_text = synced_lrc.strip() if synced_lrc else ""
    if not lrc_text:
        return False, "Empty LRC text"
    plain = plain_lyrics.strip() if plain_lyrics else ""

    # MP3: use SYLT and USLT
    if ext == ".mp3":
        try:
            from mutagen.id3 import ID3, USLT, SYLT, Encoding
            from mutagen.mp3 import MP3
            # Load or create ID3
            try:
                tags = ID3(str(p))
            except Exception:
                tags = ID3()
            # Remove existing SYLT/USLT to avoid duplicates
            tags.delall("SYLT")
            tags.delall("USLT")
            # Build SYLT: need to parse LRC into (text, timestamp) pairs
            # SYLT expects list of (text, timestamp_ms)
            import re
            sylt_data = []
            for line in lrc_text.splitlines():
                m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)", line.strip())
                if m:
                    mn, sec, txt = m.groups()
                    ms = int((int(mn) * 60 + float(sec)) * 1000)
                    sylt_data.append((txt.strip(), ms))
                elif line.strip():
                    sylt_data.append((line.strip(), 0))
            if sylt_data:
                # SYLT requires lang, format, type, desc
                tags.add(SYLT(encoding=Encoding.UTF8, lang="eng", format=2, type=1, text=sylt_data, desc=""))
            # Also add USLT with full synced text for compatibility
            tags.add(USLT(encoding=Encoding.UTF8, lang="eng", desc="", text=lrc_text))
            tags.save(str(p))
            return True, f"Embedded SYLT/USLT into {p.name}"
        except Exception as e:
            return False, str(e)

    # FLAC
    if ext == ".flac":
        try:
            from mutagen.flac import FLAC
            audio = FLAC(str(p))
            # FLAC Vorbis comments: use LYRICS and SYNCEDLYRICS
            audio["LYRICS"] = lrc_text
            # Also set unsynced plain if provided
            if plain:
                audio["UNSYNCEDLYRICS"] = plain
            audio.save()
            return True, f"Embedded LYRICS into {p.name}"
        except Exception as e:
            return False, str(e)

    # OGG / OPUS
    if ext in (".ogg", ".opus"):
        try:
            from mutagen.oggvorbis import OggVorbis
            from mutagen.oggopus import OggOpus
            audio = OggVorbis(str(p)) if ext == ".ogg" else OggOpus(str(p))
            audio["LYRICS"] = lrc_text
            audio.save()
            return True, f"Embedded LYRICS into {p.name}"
        except Exception as e:
            # fallback try generic
            try:
                from mutagen import File
                audio = File(str(p), easy=False)
                if audio is not None:
                    audio["LYRICS"] = [lrc_text]
                    audio.save()
                    return True, f"Embedded LYRICS into {p.name}"
            except Exception as e2:
                return False, f"{e} / {e2}"
            return False, str(e)

    # M4A / MP4
    if ext in (".m4a", ".mp4", ".aac"):
        try:
            from mutagen.mp4 import MP4
            audio = MP4(str(p))
            # Use \xa9lyr for lyrics (common) and also "----:com.apple.iTunes:LYRICS" style
            audio["\xa9lyr"] = [lrc_text]
            audio.save()
            return True, f"Embedded ©lyr into {p.name}"
        except Exception as e:
            return False, str(e)

    # WAV / others: try generic mutagen File + fallback to ID3-like
    try:
        from mutagen import File
        audio = File(str(p))
        if audio is not None and hasattr(audio, "tags"):
            # attempt
            if audio.tags is None:
                audio.add_tags()
            audio["LYRICS"] = lrc_text
            audio.save()
            return True, f"Embedded LYRICS into {p.name}"
    except Exception as e:
        return False, str(e)

    return False, f"Unsupported format for embedding: {ext}"
