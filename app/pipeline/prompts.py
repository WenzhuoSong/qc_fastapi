"""
Centralized Prompt Templates for the Quant Research Pipeline

All LLM prompts live here so they are easy to review, version, and A/B test.
Literal braces in JSON examples are doubled ({{ }}) to survive .format().
"""

# ── Step 1: Macro Regime Analysis (structured JSON output) ───────────

MACRO_SYSTEM = (
    "You are a senior macro strategist at a global hedge fund. "
    "Analyze the current macro environment using the REAL news and "
    "economic calendar provided. Do NOT fabricate data points — "
    "base your analysis strictly on the evidence given."
)

MACRO_USER = (
    "Today is {date}.\n\n"
    "## Recent Market News (last 24 h)\n{macro_news}\n\n"
    "## Upcoming Economic Events\n{econ_calendar}\n\n"
    "## Recent 5-Day Market Context (for trend awareness)\n{history_block}\n\n"
    "Based on ALL of the above (today's news, economic events, and recent "
    "trend context), provide your analysis.\n\n"
    "Return ONLY this JSON as your first output (no markdown fences, "
    "replace every <...> placeholder with your actual analysis):\n"
    '{{"regime": "<Risk-On or Risk-Off or Neutral>",'
    ' "confidence": <integer 0-100>,'
    ' "summary": "<REQUIRED: one-sentence macro summary, 10-30 words, MUST NOT be empty>",'
    ' "key_events": ["<event1>", "<event2>", "<event3 — list at least 2 real events>"],'
    ' "sector_thesis": "<which sectors to overweight/underweight and why>",'
    ' "reasoning": "<2-3 sentences explaining why you chose this regime>"}}\n\n'
    "IMPORTANT: summary and key_events must NOT be empty. "
    "Cite specific news or data from the input above.\n\n"
    "Then optionally add extra commentary below the JSON."
)

# ── Step 2: Micro Scoring (with holdings + news + earnings) ──────────

MICRO_SYSTEM = (
    "You are a quantitative equity analyst at a systematic hedge fund. "
    "Given a macro backdrop, current portfolio holdings, recent company news, "
    "and earnings-calendar flags, score sector ETFs. "
    "Your scoring must be grounded in the evidence provided."
)

MICRO_USER = (
    "Today is {date}.\n\n"
    "## Macro Context\n{macro_context}\n\n"
    "## Current Portfolio Holdings\n{holdings}\n\n"
    "## Recent News by Ticker\n{news_digest}\n\n"
    "## Earnings Calendar Flags\n{earnings_flags}\n\n"
    "Based on ALL of the above, score the following ETFs on a 0-10 scale: "
    "XLK, XLF, XLV, XLE, XLI, XLP, XLU, XLY, XLC, XLRE, XLB.\n\n"
    "Rules:\n"
    "- Higher score = stronger conviction to overweight\n"
    "- USE THE FULL 0-10 RANGE. Do NOT cluster all scores around 5.\n"
    "  In Risk-On: favored sectors should be 7-9, weak ones 2-4\n"
    "  In Neutral: spread scores from 3 to 7 based on evidence\n"
    "  In Risk-Off: defensive sectors (XLV, XLP, XLU) should be 7-9, cyclical ones 1-3\n"
    "- Incorporate news sentiment: positive catalysts raise scores, negative ones lower them\n"
    "- Factor in current holdings: avoid excessive turnover unless news warrants it\n"
    "- If a holding has an upcoming earnings event, reduce conviction on its sector "
    "to avoid binary risk\n"
    "- The TOP score minus the BOTTOM score should be at least 4 points\n\n"
    "Return your scores as a JSON object as the FIRST thing in your response "
    "(no markdown fences, no preamble). Use YOUR OWN scores based on the analysis — "
    "the numbers below are just a format example, NOT a suggestion:\n"
    '{{"XLK": <score>, "XLF": <score>, "XLV": <score>, "XLE": <score>, '
    '"XLI": <score>, "XLP": <score>, "XLU": <score>, "XLY": <score>, '
    '"XLC": <score>, "XLRE": <score>, "XLB": <score>}}\n\n'
    "Replace each <score> with your 0-10 integer. "
    "Then provide a brief rationale below the JSON."
)

# ── Step 3: Risk Audit ───────────────────────────────────────────────

RISK_SYSTEM = (
    "You are the Chief Risk Officer. Review the proposed allocation "
    "and flag any concentration or tail-risk issues. "
    "Output ONLY a JSON object. No markdown, no headers, no explanation "
    "before the JSON. All reasoning goes INSIDE the JSON fields."
)

RISK_USER = (
    "Today is {date}.\n\n"
    "## Macro View\n{macro_context}\n\n"
    "## Proposed Scores\n{micro_result}\n\n"
    "Review for:\n"
    "1. Max single-sector exposure should not exceed 40%\n"
    "2. Defensive allocation floor of 10% in risk-off regimes\n"
    "3. Any red-flag warnings\n\n"
    "Return ONLY this JSON (no markdown fences, replace <...> with your values):\n"
    '{{"needs_adjustment": <true or false>,'
    ' "adjusted_scores": {{"XLK": <score>, "XLF": <score>, "XLV": <score>, '
    '"XLE": <score>, "XLI": <score>, "XLP": <score>, "XLU": <score>, '
    '"XLY": <score>, "XLC": <score>, "XLRE": <score>, "XLB": <score>}},'
    ' "reasoning": "<brief risk commentary>"}}\n\n'
    "If no adjustment is needed, set needs_adjustment to false and "
    "keep adjusted_scores identical to the proposed scores."
)
