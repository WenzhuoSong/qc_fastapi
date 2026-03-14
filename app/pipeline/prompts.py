"""
Centralized Prompt Templates for the Quant Research Pipeline

All LLM prompts live here so they are easy to review, version, and A/B test.
"""

MACRO_SYSTEM = (
    "You are a senior macro strategist at a global hedge fund. "
    "Analyze the current macro environment and provide a concise directional view."
)

MACRO_USER = (
    "Today is {date}. Based on the latest macro indicators, Fed policy, "
    "geopolitical risks, and market sentiment, provide:\n"
    "1. Overall market regime (risk-on / risk-off / neutral)\n"
    "2. Sector rotation thesis (which sectors to overweight / underweight)\n"
    "3. Key risks to monitor this week\n\n"
    "Be concise and actionable."
)

MICRO_SYSTEM = (
    "You are a quantitative equity analyst. Given a macro backdrop, "
    "score individual sector ETFs and produce allocation weights."
)

MICRO_USER = (
    "Today is {date}.\n\n"
    "## Macro Context\n{macro_result}\n\n"
    "Based on this macro view, score the following ETFs on a 0-10 scale: "
    "XLK, XLF, XLV, XLE, XLI, XLP, XLU, XLY, XLC, XLRE, XLB.\n"
    "Provide a JSON object mapping ticker to raw score."
)

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
    "Return adjusted scores if needed, plus a brief risk commentary."
)
