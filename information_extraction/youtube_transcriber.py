"""
youtube_transcriber.py

Importable module to:
1) Download YouTube audio (yt-dlp) WITHOUT postprocessing.
2) Auto-detect source language and translate to English.
3) Return transcript text only.

Notes:
- We avoid yt-dlp postprocessing so ffprobe is NOT required.
- Whisper/Faster-Whisper still need ffmpeg to decode audio; we auto-use imageio-ffmpeg.
- You can pass your own ffmpeg path via ffmpeg_location.

Dependencies:
  pip install yt-dlp faster-whisper imageio-ffmpeg
  (optional) pip install openai-whisper
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

__all__ = ["transcribe_youtube"]

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

_SAFE_CHARS_RE = re.compile(r"[^a-zA-Z0-9._ -]")


def _sanitize(s: str) -> str:
    s = s.strip().replace("/", "-").replace("\\", "-")
    s = _SAFE_CHARS_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass(frozen=True)
class _DownloadResult:
    audio_path: Path
    title: str


# ------------------- FFmpeg handling -------------------

def _exe_name(base: str) -> str:
    return f"{base}.exe" if os.name == "nt" else base


def _prepare_ffmpeg(ffmpeg_location: Optional[str]) -> str:
    """
    Ensure ffmpeg is callable for Whisper/Faster-Whisper.

    Strategy:
    - Resolve a *real* ffmpeg executable path.
    - If the resolved binary isn't literally named 'ffmpeg(.exe)' (e.g. imageio-ffmpeg),
      create a hardlink/copy named exactly 'ffmpeg(.exe)' in a temp dir (Windows-safe).
    - Prepend that directory to PATH and set helpful env vars.

    Returns the absolute path to the real ffmpeg executable.
    """
    import tempfile

    def _ensure_real_ffmpeg_name(real_exe: Path) -> Path:
        """
        If 'real_exe' isn't literally named 'ffmpeg(.exe)', create a launcher with
        the exact expected name. On Windows we prefer a hardlink; fallback to copy.
        On POSIX we symlink; fallback to copy if symlink not permitted.
        Returns the launcher path named exactly ffmpeg(.exe).
        """
        desired_name = _exe_name("ffmpeg")
        if real_exe.name.lower() == desired_name.lower():
            return real_exe

        shim_dir = Path(tempfile.gettempdir()) / "ffmpeg-launcher"
        shim_dir.mkdir(parents=True, exist_ok=True)
        launcher = shim_dir / desired_name

        if launcher.exists():
            return launcher

        try:
            if os.name == "nt":
                # Hardlink is ideal (atomic, no extra space). Falls back to copy2.
                os.link(str(real_exe), str(launcher))
            else:
                launcher.symlink_to(real_exe)
        except Exception:
            shutil.copy2(str(real_exe), str(launcher))

        return launcher

    def _export_env(real_exe: Path, launcher_exe: Path) -> None:
        """
        Put the launcher's directory at the front of PATH and set env hints
        pointing to the real executable (for libraries that read them).
        """
        os.environ["PATH"] = str(launcher_exe.parent) + os.pathsep + os.environ.get("PATH", "")
        os.environ["IMAGEIO_FFMPEG_EXE"] = str(real_exe)
        os.environ["FFMPEG_BINARY"] = str(real_exe)
        os.environ["FFMPEG_PATH"] = str(real_exe)

    # 1) User-supplied path (file or folder)
    if ffmpeg_location:
        exe_path = Path(ffmpeg_location)
        if exe_path.is_dir():
            exe_path = exe_path / _exe_name("ffmpeg")
        if not exe_path.exists():
            raise RuntimeError(f"Provided ffmpeg_location does not exist: {exe_path}")
        launcher = _ensure_real_ffmpeg_name(exe_path)
        _export_env(exe_path, launcher)
        return str(exe_path)

    # 2) Bundled via imageio-ffmpeg
    try:
        import imageio_ffmpeg  # type: ignore
        exe_path = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if exe_path.exists():
            launcher = _ensure_real_ffmpeg_name(exe_path)
            _export_env(exe_path, launcher)
            return str(exe_path)
    except Exception:
        pass

    # 3) System PATH (already named correctly)
    found = shutil.which("ffmpeg")
    if found:
        exe_path = Path(found)
        _export_env(exe_path, exe_path)
        return str(exe_path)

    # 4) Not found
    raise RuntimeError(
        "FFmpeg not found. Either:\n"
        " - pip install imageio-ffmpeg (recommended), or\n"
        " - install a system ffmpeg and pass ffmpeg_location (folder or full path)."
    )


# ------------------- Download (no postprocessing; no ffprobe needed) -------------------
def _download_audio_to_temp(
    youtube_url: str,
    tmp_dir: Path,
    ffmpeg_location: Optional[str] = None,
) -> _DownloadResult:
    """
    Download the best available audio stream using yt-dlp into tmp_dir.
    We DO NOT run FFmpeg postprocessors (no ffprobe needed).
    The downloaded file will be whatever container YouTube provides (.webm/.m4a/...).
    """
    try:
        import yt_dlp  # type: ignore
    except ImportError as e:
        raise RuntimeError("yt-dlp is not installed. Run: pip install yt-dlp") from e

    # Ensure ffmpeg is ready for the transcription engines
    _prepare_ffmpeg(ffmpeg_location)

    ydl_opts = {
        "format": "bestaudio/best",
        "paths": {"home": str(tmp_dir)},      # all files land in tmp_dir
        "outtmpl": "%(title)s.%(ext)s",       # final leaf name
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "windowsfilenames": True,
        # No postprocessors -> no ffprobe requirement
    }

    def _extract_filepath_from_info(info_dict) -> Optional[Path]:
        # Most reliable in modern yt-dlp: requested_downloads
        for item in info_dict.get("requested_downloads") or []:
            fp = item.get("filepath") or item.get("filename")
            if fp:
                p = Path(fp)
                if not p.is_absolute():
                    p = tmp_dir / fp
                if p.exists():
                    return p

        # Fallback: scan for plausible audio outputs in tmp_dir
        title = info_dict.get("title") or ""
        safe_title = _sanitize(title)
        for f in tmp_dir.glob("*"):
            if f.suffix.lower() in {".webm", ".m4a", ".mp3", ".wav", ".aac", ".opus"}:
                if not safe_title or safe_title in f.stem:
                    return f
        return None

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)

    # If it was a playlist-like result, unwrap first entry
    if "entries" in info and info["entries"]:
        info = info["entries"][0]

    audio_path = _extract_filepath_from_info(info)
    if not audio_path or not audio_path.exists():
        raise FileNotFoundError("Audio file not found after download (unexpected yt-dlp output).")

    title = _sanitize(info.get("title") or audio_path.stem)
    return _DownloadResult(audio_path=audio_path, title=title)


# ------------------- Engines -------------------

def _detect_device_for_faster() -> Tuple[str, str]:
    device, compute_type = "cpu", "int8"
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            device, compute_type = "cuda", "float16"
    except Exception:
        pass
    return device, compute_type


def _transcribe_with_whisper(audio_path: Path, model_size: str) -> str:
    """
    Use openai-whisper to auto-detect language and translate to English.
    Returns transcript text (English).
    """
    try:
        import whisper  # type: ignore
        import torch  # type: ignore
    except ImportError as e:
        raise RuntimeError("openai-whisper is not installed. Run: pip install openai-whisper") from e

    device = "cuda" if torch.cuda.is_available() else "cpu"
    fp16 = device == "cuda"

    model = whisper.load_model(model_size, device=device)
    result = model.transcribe(
        str(audio_path),
        task="translate",  # -> English
        language=None,     # auto-detect
        fp16=fp16
    )
    return (result.get("text") or "").strip()


def _transcribe_with_faster_whisper(audio_path: Path, model_size: str) -> str:
    """
    Use faster-whisper to auto-detect language and translate to English.
    Returns transcript text (English).
    """
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as e:
        raise RuntimeError("faster-whisper is not installed. Run: pip install faster-whisper") from e

    device, compute_type = _detect_device_for_faster()
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    segments, _info = model.transcribe(
        str(audio_path),
        task="translate",   # -> English
        language=None,      # auto-detect
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    parts = [s.text.strip() for s in segments]
    return " ".join(p for p in parts if p).strip()


# ------------------- Public API -------------------

def transcribe_youtube(
    youtube_url: str,
    *,
    engine: str = "faster-whisper",
    model: str = "small",
    ffmpeg_location: Optional[str] = None,
    keep_temp: bool = False,
) -> str:
    """
    Download audio from a YouTube URL, auto-detect the spoken language,
    translate to English, and return the transcript text.

    Parameters
    ----------
    youtube_url : str
        Full YouTube video URL.
    engine : {"faster-whisper", "whisper"}, default "faster-whisper"
        Transcription backend to use.
    model : str, default "small"
        Model size/name.
    ffmpeg_location : Optional[str], default None
        Path to ffmpeg. If omitted, tries imageio-ffmpeg bundled binary, then system PATH.
    keep_temp : bool, default False
        If True, leaves the downloaded audio file in ./yt_transcriber_temp for debugging.

    Returns
    -------
    str
        The English transcript text.
    """
    if engine not in {"faster-whisper", "whisper"}:
        raise ValueError('engine must be one of: "faster-whisper", "whisper"')

    with tempfile.TemporaryDirectory(prefix="yt-transcribe-") as td:
        tmp_dir = Path(td)
        dl = _download_audio_to_temp(youtube_url, tmp_dir, ffmpeg_location=ffmpeg_location)

        try:
            if engine == "whisper":
                text = _transcribe_with_whisper(dl.audio_path, model)
            else:
                text = _transcribe_with_faster_whisper(dl.audio_path, model)
        finally:
            if keep_temp:
                persist_dir = Path.cwd() / "yt_transcriber_temp"
                persist_dir.mkdir(exist_ok=True)
                safe_name = _sanitize(dl.title) or "audio"
                target = persist_dir / f"{safe_name}{dl.audio_path.suffix}"
                try:
                    dl.audio_path.replace(target)
                    logger.info("Kept temp audio at: %s", target)
                except Exception as e:
                    logger.debug("Failed to keep temp audio: %s", e)

        return text


# ------------------- CLI -------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Download YT audio and transcribe to English.")
    p.add_argument("url", help="YouTube video URL")
    p.add_argument("--engine", choices=["faster-whisper", "whisper"], default="faster-whisper",
                   help="Transcription backend (default: faster-whisper)")
    p.add_argument("--model", default="small", help="Model size/name (default: small)")
    p.add_argument("--ffmpeg-location", default=None,
                   help="Folder or full path to ffmpeg binary (optional)")
    p.add_argument("--keep-temp", action="store_true", help="Keep downloaded audio file")
    p.add_argument("-v", "--verbose", action="count", default=0,
                   help="Increase verbosity (-v, -vv)")
    return p


def _configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def main() -> None:
    args = _build_arg_parser().parse_args()
    _configure_logging(args.verbose)

    text = transcribe_youtube(
        args.url,
        engine=args.engine,
        model=args.model,
        ffmpeg_location=args.ffmpeg_location,
        keep_temp=args.keep_temp,
    )
    print(text)


if __name__ == "__main__":
    # 1) Make ffmpeg resolvable *before* checking/using it.
    real_ffmpeg = _prepare_ffmpeg(None)  # uses imageio-ffmpeg if present, else PATH

    # 2) Quick verification (both by name and by absolute path)
    import subprocess
    print("ffmpeg on PATH:", shutil.which("ffmpeg") or "NOT FOUND")
    try:
        print(subprocess.check_output(["ffmpeg", "-version"], stderr=subprocess.STDOUT, text=True).splitlines()[0])
        print(subprocess.check_output([real_ffmpeg, "-version"], stderr=subprocess.STDOUT, text=True).splitlines()[0])
    except Exception as e:
        print("ffmpeg check failed:", e)
        raise

    # 3) Demo transcription (use tiny first to validate pipeline fast)
    print(
        transcribe_youtube(
            "https://www.youtube.com/watch?v=hDNiNdsPHNA",
            engine="faster-whisper",
            model="tiny",
            keep_temp=False,
        )
    )
