"""
Centralized Prompt Templates for the Quant Research Pipeline

All LLM prompts live here so they are easy to review, version, and A/B test.
Literal braces in JSON examples are doubled ({{ }}) to survive .format().
"""

# ── Step 1: Macro Regime Analysis ────────────────────────────────────

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
    "Based on the above, provide:\n"
    "1. Overall market regime (risk-on / risk-off / neutral)\n"
    "2. Sector rotation thesis (which sectors to overweight / underweight)\n"
    "3. Key risks to monitor this week\n\n"
    "Be concise and actionable. Ground every claim in the news provided."
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
    "## Macro Context\n{macro_result}\n\n"
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
    "You MUST return EXACTLY this JSON format as the FIRST thing in your response "
    "(no markdown fences, no preamble):\n"
    '{{"XLK": 7, "XLF": 6, "XLV": 5, "XLE": 4, "XLI": 5, '
    '"XLP": 3, "XLU": 2, "XLY": 6, "XLC": 5, "XLRE": 3, "XLB": 4}}\n\n'
    "Then provide a brief rationale below the JSON."
)

# ── Step 3: Risk Audit ───────────────────────────────────────────────

RISK_SYSTEM = (
    "You are the Chief Risk Officer. Review the proposed allocation "
    "and flag any concentration or tail-risk issues."
)

RISK_USER = (
    "Today is {date}.\n\n"
    "## Macro View\n{macro_result}\n\n"
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
