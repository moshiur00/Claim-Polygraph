from llm_wrapper import prompt_builder, llm_inference
from information_extraction import youtube_transcriber

def fact_check(paragraph: str | None):
    prompt = prompt_builder.build_factcheck_prompt(paragraph, min_sources=2, output_format="json")
    return llm_inference.generate_response_with_search(prompt)


# --- Example usage ---
if __name__ == "__main__":
    #paragraph = "Coffee dehydrates you. The WHO was founded in 1948."
    paragraph = youtube_transcriber.transcribe_youtube(
            "https://www.youtube.com/watch?v=hDNiNdsPHNA",
            engine="faster-whisper",
            model="tiny",
            keep_temp=False,
        )
    print(fact_check(paragraph))