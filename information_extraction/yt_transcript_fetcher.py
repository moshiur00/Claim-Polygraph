from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api._errors import CouldNotRetrieveTranscript
import re


def get_youtube_transcript_any(video_id: str):
    """
    Try to fetch a transcript in English (if available), else fall back to any language.
    Returns a dict with:
       {
         "language_code": str,
         "transcript": [ { "text": str, "start": float, "duration": float }, ... ]
       }
    Or returns None if no transcript is available.
    """
    try:
        # create API instance
        api = YouTubeTranscriptApi()
        # list available transcripts
        transcript_list = api.list(video_id)

        # Try English first
        try:
            transcript = transcript_list.find_transcript(['en'])
        except NoTranscriptFound:
            # fallback: pick first available transcript
            transcript = None
            for t in transcript_list:
                transcript = t
                break
            if transcript is None:
                # no transcripts at all
                return None

        # fetch transcript
        fetched = transcript.fetch()

        # convert fetched to raw text only
        try:
            # some transcripts return wrapper with .to_raw_data()
            raw_data = fetched.to_raw_data()
        except Exception:
            # already list of dicts
            raw_data = fetched

        # concatenate only the text fields
        raw = "".join(sn["text"] for sn in raw_data)
        # remove anything inside square brackets (e.g. [Music])
        raw = re.sub(r"\[.*?\]", "", raw)

        return {
            "language_code": transcript.language_code,
            "transcript": raw
        }

    except TranscriptsDisabled:
        print(f"[!] Transcripts are disabled for video {video_id}")
        return None
    except NoTranscriptFound:
        print(f"[!] No transcript found for video {video_id}")
        return None
    except CouldNotRetrieveTranscript as e:
        print(f"[!] Could not retrieve transcript for video {video_id}: {e}")
        return None
    except Exception as e:
        print(f"[!] Unexpected error for video {video_id}: {e}")
        return None


def extract_video_id(url: str) -> str:
    if "youtu.be/" in url:
        return url.split("youtu.be/")[-1].split("?")[0]
    if "v=" in url:
        return url.split("v=")[-1].split("&")[0]
    raise ValueError(f"Could not parse video id from URL: {url}")


if __name__ == "__main__":
    # url = "https://www.youtube.com/watch?v=bE6URTjUoYY"
    url = "https://www.youtube.com/watch?v=rr4cRS2gwsY"
    vid = extract_video_id(url)
    result = get_youtube_transcript_any(vid)
    if not result:
        print("No transcript available.")
    else:
        print("Transcript in language:", result["language_code"])
        # for entry in result["transcript"]:
        #     print(f"[{entry['start']:.2f} +{entry['duration']:.2f}] {entry['text']}")
        print (result["transcript"])