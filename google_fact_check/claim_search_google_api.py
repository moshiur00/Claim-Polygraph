import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
FACT_CHECK_API_KEY = os.getenv("FACT_CHECK_API_KEY")  # <- add to your .env
FACTCHECK_ENDPOINT = os.getenv("FACTCHECK_ENDPOINT", "https://factchecktools.googleapis.com/v1alpha1/claims:search")

def search_fact_checks(query, language="en", max_results=5):
    """
    Search fact checks using Google's Fact Check Tools API.
    
    Args:
        query (str): The search term or claim to fact-check.
        language (str): Language code (default: "en").
        max_results (int): Number of results to return (default: 5).
        
    Returns:
        list: A list of dictionaries containing fact-check info.
    """
    params = {
        "query": query,
        "languageCode": language,
        "pageSize": max_results,
        "key": FACT_CHECK_API_KEY
    }
    
    response = requests.get(FACTCHECK_ENDPOINT, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code} - {response.text}")
    
    data = response.json()
    results = []
    
    for claim in data.get("claims", []):
        claim_text = claim.get("text", "No claim text")
        claim_date = claim.get("claimDate", "Unknown date")
        
        for review in claim.get("claimReview", []):
            results.append({
                "claim": claim_text,
                "date": claim_date,
                "publisher": review.get("publisher", {}).get("name", "Unknown publisher"),
                "title": review.get("title", "No title"),
                "url": review.get("url", "No URL"),
                "rating": review.get("textualRating", "No rating")
            })
    
    return results

# # Example usage
# if __name__ == "__main__":
#     query = "COVID-19 vaccine causes infertility"
#     fact_checks = search_fact_checks(query)
    
#     if not fact_checks:
#         print("No fact checks found.")
#     else:
#         for idx, fc in enumerate(fact_checks, 1):
#             print(f"\nResult {idx}:")
#             print(f"Claim: {fc['claim']}")
#             print(f"Date: {fc['date']}")
#             print(f"Publisher: {fc['publisher']}")
#             print(f"Title: {fc['title']}")
#             print(f"URL: {fc['url']}")
#             print(f"Rating: {fc['rating']}")
