import os
import requests
from dotenv import load_dotenv
import json
import ast
from claim_processing import claim_extraction
from google_fact_check import claim_search_google_api
from information_extraction import youtube_transcriber

if __name__ == "__main__":
    

    paragraph = youtube_transcriber.transcribe_youtube(
            "https://www.youtube.com/watch?v=hDNiNdsPHNA",
            engine="faster-whisper",
            model="tiny",
            keep_temp=False,
        )

    claims = claim_extraction.extract_claims(paragraph)
    claim_list = ast.literal_eval(claims)
    print(claim_list)

    # Run fact check for each claim
    fact_checks = []
    for claim in claim_list:
        fact_checks = claim_search_google_api.search_fact_checks(claim)
        
        if not fact_checks:
            print("No fact checks found.")
        else:
            for idx, fc in enumerate(fact_checks, 1):
                print(f"\nResult {idx}:")
                print(f"Claim: {fc['claim']}")
                print(f"Date: {fc['date']}")
                print(f"Publisher: {fc['publisher']}")
                print(f"Title: {fc['title']}")
                print(f"URL: {fc['url']}")
                print(f"Rating: {fc['rating']}")



    

    