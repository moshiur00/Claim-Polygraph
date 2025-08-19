from llm_wrapper import prompt_builder
from llm_wrapper import llm_inference
from claim_processing import claim_worthiness


def check_worth_paragraph(paragraph: str | None):
    top_results = claim_worthiness.top_checkworthy_sentences(paragraph, api_key=None, top_k=3)
    check_worth_paragraph = [sent for sent, _ in top_results]
    return check_worth_paragraph

def extract_claims(paragraph: str | None):
    check_worth_paragraph_to_claim = check_worth_paragraph(paragraph)
    prompt = prompt_builder.build_prompt_to_extract_Claims(check_worth_paragraph_to_claim)
    return llm_inference.generate_response_40(prompt)
