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
    ' "summary": "<one-sentence macro summary, max 100 words>",'
    ' "key_events": ["<event1>", "<event2>", "<event3>"],'
    ' "sector_thesis": "<which sectors to overweight/underweight and why>",'
    ' "reasoning": "<2-3 sentences explaining why you chose this regime>"}}\n\n'
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
    "- Incorporate news sentiment: positive catalysts raise scores, negative ones lower them\n"
    "- Factor in current holdings: avoid excessive turnover unless news warrants it\n"
    "- If a holding has an upcoming earnings event, reduce conviction on its sector "
    "to avoid binary risk\n\n"
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
    "and flag any concentration or tail-risk issues."
)

RISK_USER = (
    "Today is {date}.\n\n"
    "## Macro View\n{macro_context}\n\n"
    "## Proposed Scores\n{micro_result}\n\n"
    "Review for:\n"
    "1. Max single-sector exposure should not exceed 40%\n"
    "2. Defensive allocation floor of 10% in risk-off regimes\n"
    "3. Any red-flag warnings\n\n"
    "If adjustments are needed, return the adjusted scores as a JSON object "
    "with the SAME format:\n"
    '{{"XLK": 7, "XLF": 6, "XLV": 5, ...}}\n\n'
    "If no adjustments are needed, state that clearly without a JSON block. "
    "Follow with a brief risk commentary."
)
