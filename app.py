from flask import Flask, render_template, request, flash
from processor import process_input
import os, json
from llm_as_fact_checker import llm_fact_checker
from claim_processing import claim_extraction
from google_fact_check import claim_search_google_api
from claim_processing import claim_worthiness
import ast

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")

@app.route("/", methods=["GET", "POST"])
def index():
    text = None
    warnings = []
    raw_input = ""
    factcheck = None   # <-- will hold JSON dict
    fact_checks = None
    claim_worthy = None

    if request.method == "POST":
        raw_input = request.form.get("user_input", "")

        # 1) Extracted text pipeline
        if raw_input:
            try:
                extracted_text, _, w = process_input(raw_input)
                text = extracted_text
                factcheckText = llm_fact_checker.fact_check(text)
                factcheck = json.loads(factcheckText)

                # New
                claim_worthy = claim_worthiness.top_checkworthy_sentences(text, api_key=None, top_k=3)
                claims = claim_extraction.extract_claims(text)
                claim_list = ast.literal_eval(claims)
                print(claim_list)
                for claim in claim_list:
                    fact_checks = claim_search_google_api.search_fact_checks(claim)
                    print(fact_checks)
                
                warnings = w
            except Exception as e:
                flash(str(e), "error")

    return render_template(
        "index.html",
        text=text,
        warnings=warnings,
        raw_input=raw_input,
        factcheck=factcheck,
        fact_checks=fact_checks,
        claim_worthy = claim_worthy
    )

if __name__ == "__main__":
    app.run()
