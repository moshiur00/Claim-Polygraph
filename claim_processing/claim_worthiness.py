#!/usr/bin/env python3
"""
Top check-worthiness sentences from paragraphs via ClaimBuster.

Usage:
  - Put your API key in the CLAIMBUSTER_API_KEY environment variable
    or pass it to top_checkworthy_sentences(text, api_key).
  - Call main() to test quickly with sample paragraphs.

Notes:
  - Uses the batch endpoint: /api/v2/score/text/sentences/
  - Sentences must end with a period; we enforce that.
"""

import os
import re
import json
import requests
from typing import List, Tuple, Optional
import nltk
from nltk.tokenize import sent_tokenize
from dotenv import load_dotenv
from information_extraction.text_from_web import get_all_text_from_url

CLAIMBUSTER_BATCH_URL = "https://idir.uta.edu/claimbuster/api/v2/score/text/sentences/"
load_dotenv()
CLAIMBUSTER_API_KEY = os.getenv("CLAIMBUSTER_API_KEY")


def _ensure_nltk_punkt():        
    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download("punkt", quiet=True)
   

def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences. Prefer NLTK if available; else use a regex fallback.
    Ensures each sentence ends with a terminal period '.' as required by the API.
    """
    text = text.strip()
    if not text:
        return []

    sentences: List[str] = []
    _ensure_nltk_punkt()
    try:
        sentences = sent_tokenize(text)
    except Exception:
        sentences = []  # fallback to regex below

    if not sentences:
        # Simple regex fallback: split on ., !, ? followed by space or end
        # and keep the delimiter.
        parts = re.split(r'([.!?])', text)
        sentences = []
        for i in range(0, len(parts) - 1, 2):
            s = (parts[i] + parts[i+1]).strip()
            if s:
                sentences.append(s)
        # If trailing chunk without punctuation
        if len(parts) % 2 == 1 and parts[-1].strip():
            sentences.append(parts[-1].strip())

    # Normalize whitespace and ensure trailing period
    normed = []
    for s in sentences:
        s = re.sub(r'\s+', ' ', s).strip()
        if not s:
            continue
        if not s.endswith("."):
            # If it already ends with "!" or "?", replace with "."
            if s.endswith(("!", "?")):
                s = s[:-1] + "."
            else:
                s = s + "."
        normed.append(s)
    return normed

def score_sentences(sentences: List[str], api_key: str) -> List[Tuple[str, float]]:
    """
    Send sentences to ClaimBuster batch endpoint and return (sentence, score).
    Handles both expected response shapes.
    """
    if not sentences:
        return []
    input_text = " ".join(s.strip() for s in sentences if s.strip())
    headers = {"x-api-key": api_key}
    payload = {"input_text": input_text}

    resp = requests.post(CLAIMBUSTER_BATCH_URL, json=payload, headers=headers, timeout=30)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise SystemExit(f"ClaimBuster API error: {e} | Body: {resp.text[:500]}")

    data = resp.json()

    # The API typically returns a list of objects or a mapping; handle both robustly.
    results: List[Tuple[str, float]] = []

    if isinstance(data, list):
        # e.g., [{"sentence": "...", "score": 0.87}, ...]
        for item in data:
            if isinstance(item, dict):
                sent = item.get("sentence") or item.get("text") or ""
                score = item.get("score") or item.get("checkworthiness") or item.get("value")
                if sent and isinstance(score, (int, float)):
                    results.append((sent, float(score)))
    elif isinstance(data, dict):
        # e.g., {"sentence -> score": 0.87, ...} or {"results":[...]}
        if "results" in data and isinstance(data["results"], list):
            for item in data["results"]:
                if isinstance(item, dict):
                    sent = item.get("sentence") or item.get("text") or ""
                    score = item.get("score") or item.get("checkworthiness") or item.get("value")
                    if sent and isinstance(score, (int, float)):
                        results.append((sent, float(score)))
        else:
            for k, v in data.items():
                if isinstance(k, str) and isinstance(v, (int, float)):
                    results.append((k, float(v)))
    else:
        raise SystemExit(f"Unexpected API response format: {json.dumps(data)[:500]}")

    return results

def top_checkworthy_sentences(text: str, api_key: Optional[str] = None, top_k: int = 3) -> List[Tuple[str, float]]:
    """
    Full pipeline: paragraphs -> sentences -> API -> top K sentences.
    """
    api_key = api_key or os.getenv("CLAIMBUSTER_API_KEY")
    if not api_key:
        raise SystemExit("Please set CLAIMBUSTER_API_KEY env var or pass api_key argument.")

    sentences = split_into_sentences(text)
    scored = score_sentences(sentences, api_key)
    scored = [item for item in scored if item[1] >= 0.5]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:max(0, top_k)]

