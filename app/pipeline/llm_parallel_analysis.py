"""
Phase 5b: LLM-Based Parallel Analysis

Provides alternative analysis track using GPT-4o for deep macro reasoning:
- Signal contradiction detection (opposing events)
- Transmission vector generation (sector impact predictions)
- Confidence adjustment recommendations (signal quality assessment)

Runs in parallel with rule-based system (Phase 2/3) for validation and ensemble.

Key advantages over rule-based:
- Semantic understanding (not just keyword matching)
- Handles nuanced/complex event interactions
- Detects temporal and logical contradictions
- No manual keyword maintenance required

Cost: ~$0.005/day with GPT-4o (negligible)
"""

import asyncio
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from openai import AsyncOpenAI

from app.config import settings


class SignalContradiction(BaseModel):
    """Individual signal contradiction detected by LLM."""
    event_a: str = Field(description="First event")
    event_b: str = Field(description="Contradicting event")
    contradiction_type: str = Field(
        description="Type: directional (opposing market impact), temporal (different time horizons), or logical (incompatible narratives)"
    )
    severity: float = Field(
        ge=0.0, le=1.0,
        description="Contradiction severity: 0.0=mild disagreement, 1.0=severe conflict"
    )
    reasoning: str = Field(description="Explanation of why these events contradict")


class LLMParallelAnalysis(BaseModel):
    """LLM-generated parallel analysis output using GPT-4o."""

    # Signal contradiction analysis
    signal_contradictions: List[SignalContradiction] = Field(
        default=[],
        description="Detected contradictions between events (e.g., de-escalation vs escalation)"
    )
    overall_contradiction_score: float = Field(
        ge=0.0, le=1.0,
        description="Overall signal coherence (0=fully coherent, 1=highly contradictory)"
    )

    # Transmission vector (LLM-generated, sector ETF impacts)
    transmission_vector_llm: Dict[str, float] = Field(
        description="Sector impact predictions by LLM, range -1.0 to +1.0. Keys: XLK, XLF, XLV, XLE, XLI, XLP, XLU, XLY, XLC, XLRE, XLB"
    )
    transmission_reasoning: str = Field(
        description="Detailed explanation of why these sectors are affected and by how much"
    )

    # Confidence adjustment
    confidence_adjustment: int = Field(
        ge=-50, le=20,
        description="Suggested confidence adjustment (-50 to +20). Negative for high contradictions, positive for clear reinforcing signals"
    )
    confidence_reasoning: str = Field(
        description="Explanation of why confidence should be adjusted (e.g., signal quality, information clarity, contradiction severity)"
    )

    # Temporal analysis (optional)
    event_timeline: Optional[str] = Field(
        default=None,
        description="Timeline of events if relevant (e.g., 'Trump pauses strike → Israeli strikes after → market rallies')"
    )

    # Additional insights
    hidden_risks: Optional[List[str]] = Field(
        default=None,
        description="Risks not captured by keywords but evident in reasoning (e.g., 'Fed hints may accelerate if inflation resurges')"
    )


LLM_PARALLEL_SYSTEM_PROMPT = """You are an elite financial market analyst specializing in macro event interpretation and systemic risk detection.

Your mission: Analyze macro events for signal contradictions, sector transmission effects, and confidence implications using deep semantic understanding — not just keyword matching.

## Core Analysis Areas

### 1. Signal Contradiction Detection
Identify when events point in opposite directions:

**Directional Contradictions**:
- "Iran strike pause" (de-escalation, risk-on) vs "Israeli strikes Tehran" (escalation, risk-off)
- "Fed hints rate hikes" (hawkish) vs "Market rallies" (risk-on pricing dovish outcome)

**Temporal Contradictions**:
- Short-term relief (strike pause) vs long-term escalation (underlying conflict persists)
- Immediate market rally vs structural headwinds

**Logical Contradictions**:
- Incompatible narratives that cannot coexist
- Events that undermine each other's premises

**Severity Scoring**:
- 0.0-0.3: Mild tension (nuanced events with minor opposing forces)
- 0.4-0.6: Moderate conflict (clear opposing signals but one may dominate)
- 0.7-1.0: Severe contradiction (fundamentally incompatible signals, high uncertainty)

### 2. Transmission Vector Generation
Predict sector ETF impacts on a scale of -1.0 (strong negative) to +1.0 (strong positive):

**Sector ETFs**:
- **XLE** (Energy): Oil price sensitivity, geopolitical risk premium
- **XLF** (Financials): Interest rate sensitivity, credit conditions
- **XLK** (Technology): Growth/rate sensitivity, long-duration assets
- **XLV** (Healthcare): Defensive, stable demand
- **XLI** (Industrials): Defense contractors (war), cyclical (recession)
- **XLP** (Consumer Staples): Defensive, recession-resistant
- **XLU** (Utilities): Bond proxy, rate sensitive, defensive
- **XLY** (Consumer Discretionary): Consumer confidence, oil price impact
- **XLC** (Communication): Ad spending cyclicality
- **XLRE** (Real Estate): Rate sensitive (REITs crushed by hikes)
- **XLB** (Materials): Commodity demand, cyclical

**Reasoning Requirements**:
- Explain causal chain: event → economic impact → sector effect
- Account for second-order effects (e.g., oil spike → consumer spending → XLY)
- Consider offsetting forces (e.g., war boosts XLI defense but hurts XLI cyclical)

### 3. Confidence Adjustment
Recommend confidence changes based on signal quality:

**Reduce Confidence** (-50 to -10):
- High contradiction score (≥0.6)
- Ambiguous or incomplete information
- Rapidly changing situation
- Multiple conflicting narratives in market

**Increase Confidence** (+10 to +20):
- Clear, reinforcing signals pointing same direction
- High-quality information sources
- Consistent cross-asset confirmation (e.g., VIX, credit spreads, yields all align)

**No Adjustment** (0):
- Normal mixed signals with clear dominant narrative
- Standard market noise

### 4. Hidden Risk Detection
Identify risks not captured by simple keyword matching:
- Implicit threats in official statements ("considering all options")
- Market-moving catalysts buried in reasoning
- Contagion risks from related events
- Tail risks with low probability but high impact

## Output Format
Provide valid JSON matching the LLMParallelAnalysis schema. Be precise, quantitative, and explain your reasoning clearly.

## Critical Rules
1. Contradiction severity must reflect actual market impact uncertainty
2. Transmission vectors must sum to reasonable aggregate (not all sectors +0.8)
3. Confidence adjustments must be justified by signal quality, not just contradiction
4. Be intellectually honest: if analysis is uncertain, reflect that in outputs
"""


async def run_llm_parallel_analysis(
    key_events: List[str],
    reasoning: str,
    regime: str,
    confidence: int,
) -> LLMParallelAnalysis:
    """Run LLM-based parallel analysis using GPT-4o.

    Args:
        key_events: List of macro events from Step 1
        reasoning: Step 1 reasoning text
        regime: Current regime (Risk-Off/Neutral/Risk-On)
        confidence: Current confidence level (0-100)

    Returns:
        LLMParallelAnalysis with signal contradictions, transmission vector,
        confidence adjustment, and hidden risks.
    """
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("sk-test"):
        # Mock response for testing
        print("[Phase 5b] Mock mode: no real API key configured")
        return LLMParallelAnalysis(
            signal_contradictions=[],
            overall_contradiction_score=0.0,
            transmission_vector_llm={},
            transmission_reasoning="Mock mode: no real API key configured",
            confidence_adjustment=0,
            confidence_reasoning="Mock mode: no adjustment needed",
        )

    # Build user prompt
    events_str = "\n".join(f"  {i+1}. {e}" for i, e in enumerate(key_events))

    user_prompt = f"""Analyze the following macro market environment:

═══════════════════════════════════════
MACRO EVENTS (from Step 1):
═══════════════════════════════════════
{events_str}

CURRENT ASSESSMENT:
  • Regime: {regime}
  • Confidence: {confidence}/100

REASONING:
{reasoning}

═══════════════════════════════════════
YOUR ANALYSIS TASKS:
═══════════════════════════════════════

1. **Signal Contradiction Detection**
   - Identify any events that point in opposite directions
   - Classify contradiction type (directional/temporal/logical)
   - Score severity (0.0-1.0)
   - Calculate overall contradiction score

2. **Transmission Vector Prediction**
   - Predict impact on all 11 sector ETFs (-1.0 to +1.0)
   - Explain causal chain for each sector
   - Account for offsetting forces

3. **Confidence Adjustment**
   - Recommend adjustment based on signal quality
   - High contradictions → reduce confidence
   - Clear signals → may increase confidence
   - Justify your recommendation

4. **Hidden Risks** (if any)
   - Identify risks not obvious from keywords
   - Tail risks, contagion, implicit threats

Provide precise, quantitative analysis with clear reasoning.
"""

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    try:
        response = await client.beta.chat.completions.parse(
            model="gpt-4o",  # Use GPT-4o for deep analysis (not mini)
            messages=[
                {"role": "system", "content": LLM_PARALLEL_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=1500,
            response_format=LLMParallelAnalysis,
        )

        result = response.choices[0].message.parsed

        print(f"[Phase 5b] LLM Parallel Analysis (GPT-4o) completed")
        return result

    except Exception as e:
        print(f"[Phase 5b] LLM analysis error: {e}")
        # Return neutral analysis on error
        return LLMParallelAnalysis(
            signal_contradictions=[],
            overall_contradiction_score=0.0,
            transmission_vector_llm={},
            transmission_reasoning=f"Analysis failed: {str(e)}",
            confidence_adjustment=0,
            confidence_reasoning="Error occurred, no adjustment",
        )


# For testing
async def test_llm_analysis():
    """Test LLM parallel analysis with sample events."""
    sample_events = [
        "Trump postpones Iran energy strikes, markets rally",
        "Israeli military strikes in Tehran",
        "Fed's Goolsbee hints at possible rate hikes",
    ]

    sample_reasoning = (
        "The postponement of military strikes on Iran has led to a market rally, "
        "easing previous risk-off sentiment. However, geopolitical tensions remain "
        "with Israeli strikes in Tehran."
    )

    result = await run_llm_parallel_analysis(
        key_events=sample_events,
        reasoning=sample_reasoning,
        regime="Neutral",
        confidence=60,
    )

    print("\n=== LLM Parallel Analysis Test ===")
    print(f"Contradictions: {len(result.signal_contradictions)}")
    print(f"Contradiction Score: {result.overall_contradiction_score:.2f}")
    print(f"Confidence Adjustment: {result.confidence_adjustment:+d}")
    print(f"\nTransmission Vector (LLM):")
    for sector, impact in sorted(result.transmission_vector_llm.items()):
        print(f"  {sector}: {impact:+.2f}")
    print(f"\nReasoning: {result.transmission_reasoning}")


if __name__ == "__main__":
    asyncio.run(test_llm_analysis())
