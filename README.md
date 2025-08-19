# Claim-Polygraph

Claim-Polygraph is an automated pipeline for extracting, analyzing, and fact-checking claims from news articles, YouTube videos, and other sources using LLMs and external fact-checking APIs.

## Features

- **Text Extraction**: Extracts readable text from web articles and transcribes spoken content from YouTube videos.
- **Claim Identification**: Uses ClaimBuster API to find the most check-worthy sentences.
- **Claim Extraction**: Extracts concise, verifiable claims from text using LLM prompts.
- **Fact-Checking**: 
  - LLM-based fact-checking with standardized scoring and reasoning.
  - Integrates with Google Fact Check Tools API for external fact-check reviews.
- **Web Interface**: Flask-based UI for submitting text or URLs and viewing results.
- **Rich Output**: Displays claim-worthiness scores, fact-check verdicts, confidence bands, sources, and reasoning.

## Usage

- Paste raw text, a news/article URL, or a YouTube video URL into the input box.
- The system will extract text, identify claims, and run fact-checking.
- Results include:
  - Top claim-worthy sentences ([ClaimBuster](https://idir.uta.edu/claimbuster/))
  - LLM-based fact-checks with verdicts, confidence, reasoning, and sources ([OpenAI GPT](https://platform.openai.com/docs/))
  - External fact-check reviews from [Google Fact Check Tools](https://toolbox.google.com/factcheck/explorer)



## Quick Start

### Prerequisites

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) (for YouTube transcription)
- API keys for:
  - OpenAI (LLM)
  - ClaimBuster
  - Google Fact Check Tools

### Installation

```sh
git clone https://github.com/yourusername/claim-polygraph.git
cd claim-polygraph
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r [requirements.txt](http://_vscodecontentref_/0)
```

## APIs Used

- [OpenAI GPT](https://platform.openai.com/docs/)
- [ClaimBuster](https://idir.uta.edu/claimbuster/api/)
- [Google Fact Check Tools](https://developers.google.com/fact-check/tools/api/reference/rest)

## License

MIT License. See [LICENSE](LICENSE).

## Acknowledgments

- [ClaimBuster](https://idir.uta.edu/claimbuster/)
- [Google Fact Check Tools](https://toolbox.google.com/factcheck/explorer)
- [OpenAI](https://openai.com/)
