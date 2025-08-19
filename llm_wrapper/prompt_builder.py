


def build_factcheck_prompt(
    paragraph: str,
    min_sources: int = 2,
    output_format: str = "json",  # "json" or "markdown"
    include_overall_summary: bool = True,
    custom_priority_sources: list[str] | None = None,
    include_deterministic_formula: bool = True,
    top_n: int = 3,  # return up to N top claims; do NOT fabricate or pad
) -> str:
    """
    Build a robust, tool-ready prompt that:
      1) Extracts the TOP N claimworthy sentences (no padding; return fewer if fewer exist)
      2) Fact-checks each with verdict, standardized confidence score/band, reasoning, and sources
      3) Provides an overall reliability assessment with a standardized score/band (optional)
    """

    priority_sources = custom_priority_sources or [
        "PolitiFact",
        "FactCheck.org",
        "Snopes",
        "The Washington Post Fact Checker",
        "Reuters Fact Check",
        "Full Fact",
        "Quote Investigator",
        # Fallbacks:
        "official government sources",
        "peer-reviewed research",
        "major reputable news organizations",
    ]

    # --- Standardized Rubric & Scoring Instructions ---
    rubric_block = (
        "CONFIDENCE & RELIABILITY SCORING (0–100)\n"
        "Use these bands for both per-claim Confidence and Overall Reliability:\n"
        "  95–100: Established fact\n"
        "  85–94 : Very likely\n"
        "  70–84 : Likely\n"
        "  55–69 : Uncertain / Mixed\n"
        "  35–54 : Doubtful\n"
        "  15–34 : Unlikely\n"
        "  0–14  : False / Unsupported\n"
        "\n"
        "Checklist for scoring (apply to each claim and the overall text):\n"
        "  • Source Quality: primary/official > peer-reviewed > major media > other > social/blogs\n"
        "  • Independence & Count: more independent, agreeing sources → higher\n"
        "  • Consensus: alignment among reputable fact-checkers/experts → higher\n"
        "  • Recency/Relevance: current enough for the domain → higher\n"
        "  • Specificity/Verifiability: concrete, measurable claims → higher\n"
        "  • Conflict: credible contradictory evidence → lower\n"
    )

    formula_block = (
        "Deterministic scoring formula (compute 0–100 then round to nearest int):\n"
        "  Weights: SQ 0.30, IC 0.20, CS 0.20, RR 0.15, SV 0.10, Conflict Penalty (CP) −0.15\n"
        "  Sub-scores (each 0–100):\n"
        "    • SQ (Source Quality): primary/official or peer-reviewed 90–100; major media 75–89; mixed/unknown 50–74; social/blogs 0–49\n"
        "    • IC (Independence & Count): 3+ independent 95–100; 2 independent 85–94; 1 source 60–79; 0 verifiable 0–40\n"
        "    • CS (Consensus): clear alignment 90–100; minor dissent 70–89; mixed 40–69; major dissent 0–39\n"
        "    • RR (Recency/Relevance): ≤12m for fast domains 90–100; ≤24m 75–89; older-but-stable 60–79; stale for fast topics 0–59\n"
        "    • SV (Specificity/Verifiability): precise 85–100; definition-dependent 60–84; vague 0–59\n"
        "    • CP (subtract): none 0; minor conflict −5 to −8; substantial −9 to −12; strong primary-source conflict −13 to −15\n"
        "  Formula:\n"
        "    Score = 100 * (0.30*SQ + 0.20*IC + 0.20*CS + 0.15*RR + 0.10*SV) + CP\n"
        "After computing, map to band labels using the bands above.\n"
    ) if include_deterministic_formula else ""

    # --- Output format spec ---
    if output_format.lower() == "markdown":
        format_block = (
            f"Output as a Markdown table with up to {top_n} rows and columns:\n"
            "Rank | Sentence | Verdict | Confidence (0–100) | Confidence Band | Rationale | Sources (links)\n"
            "List at most the top N claimworthy sentences by importance/impact and checkability.\n"
            "If fewer than N claimworthy sentences are present, return fewer rows. Do NOT invent or pad.\n"
        )
        summary_block = (
            "\nThen add an **Overall Reliability** section with:\n"
            "- Reliability Score (0–100)\n"
            "- Reliability Band (use the same band rules)\n"
            "- One-paragraph summary (note uncertainty, conflicts, data gaps)\n"
            if include_overall_summary else ""
        )
    else:  # JSON
        format_block = (
            "Return a single JSON object with two top-level keys:\n"
            "  \"claims\": [  # length <= N; do NOT pad or fabricate\n"
            "    {\n"
            "      \"rank\": int,                        # 1 = highest-priority claim\n"
            "      \"sentence\": str,\n"
            "      \"verdict\": \"True\" | \"False\" | \"Misleading\" | \"Unverified\",\n"
            "      \"confidence\": int,                 # 0–100 via rubric (and formula if provided)\n"
            "      \"confidence_band\": str,            # Established fact | Very likely | Likely | Uncertain / Mixed | Doubtful | Unlikely | False / Unsupported\n"
            "      \"reasoning\": str,                  # 1–3 sentences explaining verdict & key evidence\n"
            "      \"sources\": [str]                   # ≥ {min_sources} URLs or site+URL strings\n"
            "    }, ...\n"
            "  ]"
        )
        summary_block = (
            ",\n  \"overall_reliability\": {\n"
            "    \"score\": int,                        # 0–100 via same rubric/formula\n"
            "    \"band\": str,                         # same band labels\n"
            "    \"summary\": str                       # one paragraph noting uncertainty/conflicts\n"
            "  }\n"
            "}\n"
            if include_overall_summary else "\n}\n"
        )
        format_block += summary_block

    # --- Instruction text ---
    instruction = f"""You are a fact-checking system.

    GOAL
    From the provided text, identify and fact-check the TOP {top_n} claimworthy sentences.
    If fewer than {top_n} claimworthy sentences exist, return only those found. DO NOT invent claims, sources, or padding.

    SELECTION RULES (Top-N)
    - A "claimworthy sentence" is a statement that can be checked against evidence.
    - Prioritize sentences that are (a) specific & measurable, (b) consequential/impactful, and (c) likely to be verifiable with reliable sources.
    - If multiple candidates qualify, rank higher those with clearer measurability and higher potential for public impact.

    TASK
    1) Extract up to {top_n} claimworthy sentences (no padding).
    Exclude opinions, vague generalities, rhetorical questions, and style-only remarks.

    2) For each selected claim, provide:
    - Rank (1 = highest priority)
    - Sentence
    - Verdict: True | False | Misleading | Unverified
    - Confidence: 0–100 using the standardized rubric below (and formula if given)
    - Confidence Band: map the numeric score to a band using the band table below
    - Reasoning: concise (1–3 sentences) explaining the verdict and key evidence
    - Sources: at least {min_sources} recent, reliable sources with direct links.
        PRIORITIZE these fact-checking authorities and then others as needed:
        {", ".join(priority_sources)}.

    3) Evidence requirements:
    - Use the most up-to-date information available.
    - Prefer primary sources (official data, documents) and reputable secondary sources.
    - If evidence is mixed or insufficient, choose "Unverified" or "Misleading" and explain why.
    - Do not fabricate sources or links. If a link is unavailable, say so and adjust the verdict.

    4) Confidence & Reliability standardization:
    {rubric_block}
    {formula_block if include_deterministic_formula else ''}\
    5) Overall assessment:
    { 'Provide a single Overall Reliability score (0–100), the corresponding band label, and a brief paragraph summarizing the overall reliability of the text (note uncertainty, conflicts, and data gaps).' if include_overall_summary else 'Overall assessment not required.' }

    OUTPUT FORMAT
    {format_block}
    TEXT TO ANALYZE
    \"\"\"{paragraph.strip()}\"\"\""""

    return instruction


def build_prompt_to_extract_Claims(paragraph: str | None):
    prompt = f"""
        You are helping with a news fact-checking pipeline.

        TASK
        Extract one verifiable claim from **each line** of the paragraph below. 
        Assume that every line contains a claim that must be extracted. 

        DEFINITION OF “CLAIM”
        A concise, self-contained factual statement that can be independently verified (e.g., who/what/where/when/how many). Avoid vague themes, opinions, or advice.

        SELECTION RULES
        - Prefer specific, time-bound, numeric, or clearly attributable statements.
        - Combine duplicates; remove near-duplicates.
        - If fewer than 5 clear claims exist, return only the ones that qualify (do not fabricate).

        OUTPUT FORMAT (IMPORTANT)
        - Return a single Python list literal of strings.
        - Use SINGLE quotes around each claim.
        - No numbering, no extra text, no code fences, no trailing comma.
        - Each claim ≤ 25 words and stands alone without needing the paragraph for context.

        EXAMPLES
        Paragraph: "City X reports 12 new measles cases; Mayor Jane Doe declares emergency; flights canceled at Airport Y."
        Output: ['City X reports 12 new measles cases.', 'Mayor Jane Doe declares an emergency in City X.', 'Flights are canceled at Airport Y.']

        NOW EXTRACT FROM THIS PARAGRAPH
        \"\"\"{paragraph}\"\"\"
    """
    return prompt.strip()


def build_factcheck_prompt_previous(
    paragraph: str,
    min_sources: int = 2,
    output_format: str = "json",  # "json" or "markdown"
    include_overall_summary: bool = True,
    custom_priority_sources: list[str] | None = None,
) -> str:
    """
    Build a robust, tool-ready prompt that instructs an AI to:
      1) Identify claimworthy sentences
      2) Fact-check each with verdict, confidence, reasoning, and sources
      3) Provide an overall reliability assessment (optional)

    Parameters
    ----------
    paragraph : str
        The input paragraph to analyze.
    min_sources : int, default=2
        Minimum number of sources to cite per claim.
    output_format : {"json", "markdown"}, default="json"
        Preferred output format for results.
    include_overall_summary : bool, default=True
        Whether to request a final reliability score and summary.
    custom_priority_sources : list[str] | None
        Optional ordered list of high-priority fact-check sources to prefer.

    Returns
    -------
    str
        A complete instruction prompt ready to send to the model.
    """
    priority_sources = custom_priority_sources or [
        "PolitiFact",
        "FactCheck.org",
        "Snopes",
        "The Washington Post Fact Checker",
        "Reuters Fact Check",
        "Full Fact",
        "Quote Investigator",
        # Fallbacks the model should also consider:
        "official government sources",
        "peer-reviewed research",
        "major reputable news organizations",
    ]

    # Structured output spec (kept short so it’s easy to parse)
    if output_format.lower() == "markdown":
        format_block = (
            "Output as a Markdown table with columns:\n"
            "Sentence | Verdict | Confidence (0–100) | Reasoning | Sources (links)\n"
            "Use one row per claimworthy sentence.\n"
        )
        summary_block = (
            "\nAt the end, add an **Overall Reliability** section with:\n"
            "- Reliability Score (0–100)\n"
            "- One-paragraph summary\n"
            if include_overall_summary else ""
        )
    else:  # JSON
        format_block = (
            "Return a single JSON object with two top-level keys:\n"
            "  \"claims\": [\n"
            "    {\n"
            "      \"sentence\": str,\n"
            "      \"verdict\": \"True\" | \"False\" | \"Misleading\" | \"Unverified\",\n"
            "      \"confidence\": int,  # 0–100\n"
            "      \"reasoning\": str,   # 1–3 sentences\n"
            "      \"sources\": [str]    # list of URLs or site+URL strings\n"
            "    }, ...\n"
            "  ]\n"
        )
        summary_block = (
            ",\n  \"overall_reliability\": {\n"
            "    \"score\": int,      # 0–100\n"
            "    \"summary\": str     # one paragraph\n"
            "  }\n"
            "}\n"
            if include_overall_summary else "\n}\n"
        )
        format_block += summary_block

    # Build the instruction text
    instruction = f"""You are a fact-checking system.

    TASK
    1) Identify all claimworthy sentences in the provided text (statements that can be checked against evidence).
    Exclude opinions, vague generalities, rhetorical questions, and style-only remarks.

    2) For each claimworthy sentence, verify it and provide:
    - Sentence
    - Verdict: True | False | Misleading | Unverified
    - Confidence: 0–100 (how certain you are in the verdict)
    - Reasoning: concise (1–3 sentences) explaining the verdict
    - Sources: at least {min_sources} recent, reliable sources with direct links.
        PRIORITIZE these fact-checking authorities and then others as needed:
        {", ".join(priority_sources)}.

    3) Evidence requirements:
    - Use the most up-to-date information available.
    - Prefer primary sources (official data, documents) and reputable secondary sources.
    - If evidence is mixed or insufficient, choose "Unverified" or "Misleading" and explain why.

    4) Transparency:
    - Be explicit about uncertainty and limits of available evidence.
    - Do not fabricate sources or links. If a link is unavailable, say so and adjust the verdict.

    5) { 'Overall assessment: provide a single reliability score (0–100) and a brief paragraph summarizing the overall reliability of the text.' if include_overall_summary else 'Overall assessment: not required.' }

    OUTPUT FORMAT
    {format_block}
    TEXT TO ANALYZE
    \"\"\"{paragraph.strip()}\"\"\""""

    return instruction


def build_factcheck_prompt_deterministic(
    paragraph: str,
    min_sources: int = 2,
    output_format: str = "json",  # "json" or "markdown"
    include_overall_summary: bool = True,
    custom_priority_sources: list[str] | None = None,
    include_deterministic_formula: bool = True,
) -> str:
    """
    Build a robust, tool-ready prompt that:
      1) Identifies claimworthy sentences
      2) Fact-checks each with verdict, standardized confidence score/band, reasoning, and sources
      3) Provides an overall reliability assessment with a standardized score/band (optional)
    """

    priority_sources = custom_priority_sources or [
        "PolitiFact",
        "FactCheck.org",
        "Snopes",
        "The Washington Post Fact Checker",
        "Reuters Fact Check",
        "Full Fact",
        "Quote Investigator",
        # Fallbacks:
        "official government sources",
        "peer-reviewed research",
        "major reputable news organizations",
    ]

    # --- Standardized Rubric & Scoring Instructions ---
    rubric_block = (
        "CONFIDENCE & RELIABILITY SCORING (0–100)\n"
        "Use these bands for both per-claim Confidence and Overall Reliability:\n"
        "  95–100: Established fact\n"
        "  85–94 : Very likely\n"
        "  70–84 : Likely\n"
        "  55–69 : Uncertain / Mixed\n"
        "  35–54 : Doubtful\n"
        "  15–34 : Unlikely\n"
        "  0–14  : False / Unsupported\n"
        "\n"
        "Checklist for scoring (apply to each claim and the overall text):\n"
        "  • Source Quality: primary/official > peer-reviewed > major media > other > social/blogs\n"
        "  • Independence & Count: more independent, agreeing sources → higher\n"
        "  • Consensus: alignment among reputable fact-checkers/experts → higher\n"
        "  • Recency/Relevance: current enough for the domain → higher\n"
        "  • Specificity/Verifiability: concrete, measurable claims → higher\n"
        "  • Conflict: credible contradictory evidence → lower\n"
    )

    formula_block = (
        "Deterministic scoring formula (compute 0–100 then round to nearest int):\n"
        "  Weights: SQ 0.30, IC 0.20, CS 0.20, RR 0.15, SV 0.10, Conflict Penalty (CP) −0.15\n"
        "  Sub-scores (each 0–100):\n"
        "    • SQ (Source Quality): primary/official or peer-reviewed 90–100; major media 75–89; mixed/unknown 50–74; social/blogs 0–49\n"
        "    • IC (Independence & Count): 3+ independent 95–100; 2 independent 85–94; 1 source 60–79; 0 verifiable 0–40\n"
        "    • CS (Consensus): clear alignment 90–100; minor dissent 70–89; mixed 40–69; major dissent 0–39\n"
        "    • RR (Recency/Relevance): ≤12m for fast domains 90–100; ≤24m 75–89; older-but-stable 60–79; stale for fast topics 0–59\n"
        "    • SV (Specificity/Verifiability): precise 85–100; definition-dependent 60–84; vague 0–59\n"
        "    • CP (subtract): none 0; minor conflict −5 to −8; substantial −9 to −12; strong primary-source conflict −13 to −15\n"
        "  Formula:\n"
        "    Score = 100 * (0.30*SQ + 0.20*IC + 0.20*CS + 0.15*RR + 0.10*SV) + CP\n"
        "After computing, map to band labels using the bands above.\n"
    ) if include_deterministic_formula else ""

    # --- Output format spec ---
    if output_format.lower() == "markdown":
        format_block = (
            "Output as a Markdown table with columns:\n"
            "Sentence | Verdict | Confidence (0–100) | Confidence Band | Rationale | Sources (links)\n"
            "Use one row per claimworthy sentence.\n"
        )
        summary_block = (
            "\nThen add an **Overall Reliability** section with:\n"
            "- Reliability Score (0–100)\n"
            "- Reliability Band (use the same band rules)\n"
            "- One-paragraph summary (note uncertainty, conflicts, data gaps)\n"
            if include_overall_summary else ""
        )
    else:  # JSON
        format_block = (
            "Return a single JSON object with two top-level keys:\n"
            "  \"claims\": [\n"
            "    {\n"
            "      \"sentence\": str,\n"
            "      \"verdict\": \"True\" | \"False\" | \"Misleading\" | \"Unverified\",\n"
            "      \"confidence\": int,                 # 0–100 computed via rubric (and formula if provided)\n"
            "      \"confidence_band\": str,            # Established fact | Very likely | Likely | Uncertain / Mixed | Doubtful | Unlikely | False / Unsupported\n"
            "      \"reasoning\": str,                  # 1–3 sentences explaining the verdict & key evidence\n"
            "      \"sources\": [str]                   # ≥ {min_sources} URLs or site+URL strings\n"
            "    }, ...\n"
            "  ]"
        )
        summary_block = (
            ",\n  \"overall_reliability\": {\n"
            "    \"score\": int,                        # 0–100 via same rubric/formula\n"
            "    \"band\": str,                         # same band labels\n"
            "    \"summary\": str                       # one paragraph noting uncertainty/conflicts\n"
            "  }\n"
            "}\n"
            if include_overall_summary else "\n}\n"
        )
        format_block += summary_block

    # --- Instruction text ---
    instruction = f"""You are a fact-checking system.

    TASK
    1) Identify all claimworthy sentences in the provided text (statements that can be checked against evidence).
    Exclude opinions, vague generalities, rhetorical questions, and style-only remarks.

    2) For each claimworthy sentence, verify it and provide:
    - Sentence
    - Verdict: True | False | Misleading | Unverified
    - Confidence: 0–100 using the standardized rubric below (and formula if given)
    - Confidence Band: map the numeric score to a band using the band table below
    - Reasoning: concise (1–3 sentences) explaining the verdict and key evidence
    - Sources: at least {min_sources} recent, reliable sources with direct links.
        PRIORITIZE these fact-checking authorities and then others as needed:
        {", ".join(priority_sources)}.

    3) Evidence requirements:
    - Use the most up-to-date information available.
    - Prefer primary sources (official data, documents) and reputable secondary sources.
    - If evidence is mixed or insufficient, choose "Unverified" or "Misleading" and explain why.
    - Do not fabricate sources or links.

    4) Confidence & Reliability standardization:
    {rubric_block}
    {formula_block if include_deterministic_formula else ''}\
    5) Overall assessment:
    { 'Provide a single Overall Reliability score (0–100), the corresponding band label, and a brief paragraph summarizing the overall reliability of the text (note uncertainty, conflicts, and data gaps).' if include_overall_summary else 'Overall assessment not required.' }

    OUTPUT FORMAT
    {format_block}
    TEXT TO ANALYZE
    \"\"\"{paragraph.strip()}\"\"\""""

    return instruction

def build_factcheck_prompt_N(
    paragraph: str,
    min_sources: int = 2,
    output_format: str = "json",  # "json" or "markdown"
    include_overall_summary: bool = True,
    custom_priority_sources: list[str] | None = None,
    top_n: int = 5,  # extract up to N claims; return fewer if fewer exist (no padding)
) -> str:
    """
    Build a robust, tool-ready prompt that instructs an AI to:
      1) Extract up to N claimworthy sentences (no padding or fabrication)
      2) Fact-check each with verdict, confidence, reasoning, and sources
      3) Provide an overall reliability assessment (optional)
    """

    priority_sources = custom_priority_sources or [
        "PolitiFact",
        "FactCheck.org",
        "Snopes",
        "The Washington Post Fact Checker",
        "Reuters Fact Check",
        "Full Fact",
        "Quote Investigator",
        # Fallbacks the model should also consider:
        "official government sources",
        "peer-reviewed research",
        "major reputable news organizations",
    ]

    # Structured output spec (kept short so it’s easy to parse)
    if output_format.lower() == "markdown":
        format_block = (
            f"Output as a Markdown table with up to {top_n} rows and columns:\n"
            "Sentence | Verdict | Confidence (0–100) | Reasoning | Sources (links)\n"
            "List at most the top N claimworthy sentences.\n"
            "If fewer than N claimworthy sentences are present, return fewer rows. Do NOT invent or pad.\n"
        )
        summary_block = (
            "\nAt the end, add an **Overall Reliability** section with:\n"
            "- Reliability Score (0–100)\n"
            "- One-paragraph summary\n"
            if include_overall_summary else ""
        )
    else:  # JSON
        format_block = (
            "Return a single JSON object with two top-level keys:\n"
            "  \"claims\": [  # length <= N; return fewer if fewer exist; do NOT pad or fabricate\n"
            "    {\n"
            "      \"sentence\": str,\n"
            "      \"verdict\": \"True\" | \"False\" | \"Misleading\" | \"Unverified\",\n"
            "      \"confidence\": int,  # 0–100\n"
            "      \"reasoning\": str,   # 1–3 sentences\n"
            "      \"sources\": [str]    # list of URLs or site+URL strings\n"
            "    }, ...\n"
            "  ]\n"
        )
        summary_block = (
            ",\n  \"overall_reliability\": {\n"
            "    \"score\": int,      # 0–100\n"
            "    \"summary\": str     # one paragraph\n"
            "  }\n"
            "}\n"
            if include_overall_summary else "\n}\n"
        )
        format_block += summary_block

    # Build the instruction text
    instruction = f"""You are a fact-checking system.

    GOAL
    Extract and fact-check the TOP {top_n} claimworthy sentences from the provided text.
    If fewer than {top_n} claimworthy sentences exist, return only those found. Do NOT invent claims or sources. Do NOT pad.

    TASK
    1) Identify up to {top_n} claimworthy sentences (statements that can be checked against evidence).
    Exclude opinions, vague generalities, rhetorical questions, and style-only remarks.

    2) For each claimworthy sentence, provide:
    - Sentence
    - Verdict: True | False | Misleading | Unverified
    - Confidence: 0–100 (how certain you are in the verdict)
    - Reasoning: concise (1–3 sentences) explaining the verdict
    - Sources: at least {min_sources} recent, reliable sources with direct links.
        PRIORITIZE these fact-checking authorities and then others as needed:
        {", ".join(priority_sources)}.

    3) Evidence requirements:
    - Use the most up-to-date information available.
    - Prefer primary sources (official data, documents) and reputable secondary sources.
    - If evidence is mixed or insufficient, choose "Unverified" or "Misleading" and explain why.

    4) Transparency:
    - Be explicit about uncertainty and limits of available evidence.
    - Do not fabricate sources or links. If a link is unavailable, say so and adjust the verdict.

    5) { 'Overall assessment: provide a single reliability score (0–100) and a brief paragraph summarizing the overall reliability of the text.' if include_overall_summary else 'Overall assessment: not required.' }

    OUTPUT FORMAT
    {format_block}
    TEXT TO ANALYZE
    \"\"\"{paragraph.strip()}\"\"\""""

    return instruction
