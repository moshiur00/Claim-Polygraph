import re
from urllib.parse import urlparse
import requests
import trafilatura
from information_extraction import youtube_transcriber

# from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

YOUTUBE_HOSTS = {"youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com"}

def is_url(text: str) -> bool:
    try:
        parsed = urlparse(text.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False

def is_youtube(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host in YOUTUBE_HOSTS

def fetch_text_from_article(url: str) -> str:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError("Could not download the page (blocked or unreachable).")
    extracted = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=False,
        favor_recall=True,
        no_fallback=False,
    )
    if not extracted:
        raise ValueError("Failed to extract article text from this URL.")
    return extracted

def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def basic_analysis(text: str) -> dict:
    """
    Minimal analysis: char/word/sentence counts, top tokens (naive).
    Keeps it dependency-light.
    """
    clean = normalize_whitespace(text)
    words = re.findall(r"\b[\w’'-]+\b", clean.lower())
    sentences = re.split(r"(?<=[.!?])\s+", clean) if clean else []
    # naive stoplist
    stop = {
        "the","a","an","and","or","of","to","in","for","on","at","with","by","is","are",
        "was","were","be","it","this","that","as","from","but","if","not","we","you",
        "i","they","he","she","them","his","her","our","their","my","your"
    }
    freq = {}
    for w in words:
        if w in stop or len(w) < 3:
            continue
        freq[w] = freq.get(w, 0) + 1
    top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]

    # super-light "summary": first 3 sentences preview
    preview = " ".join(sentences[:3]).strip()

    return {
        "characters": len(clean),
        "words": len(words),
        "sentences": len([s for s in sentences if s]),
        "top_terms": top,
        "preview": preview
    }

def process_input(user_input: str) -> tuple[str, dict, list[str]]:
    """
    Returns (final_text, analysis, warnings)
    - user_input may be plain text or URL (YouTube/news).
    """
    warnings: list[str] = []
    user_input = user_input.strip()

    if not user_input:
        raise ValueError("Empty input.")

    if is_url(user_input):
        if is_youtube(user_input):
            text = youtube_transcriber.transcribe_youtube(
                user_input,
                engine="faster-whisper",
                model="tiny",
                keep_temp=False,
            )
        else:
            text = fetch_text_from_article(user_input)
    else:
        text = user_input

    text = normalize_whitespace(text)
    if not text:
        raise ValueError("No textual content found.")

    analysis = basic_analysis(text)
    return text, analysis, warnings


