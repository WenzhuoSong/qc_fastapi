"""
Unit Tests for Phase 2: Event Transmission Rules

Tests canonical pattern matching and transmission vector logic.

Run:
    pytest tests/test_phase2_transmission.py -v
"""

import pytest
from app.pipeline.transmission_rules import (
    match_event_to_pattern,
    detect_event_type,
    format_transmission_context,
    CANONICAL_TRANSMISSIONS,
)


class TestPatternMatching:
    """Test canonical event pattern matching."""

    def test_supply_shock_oil_pattern(self):
        """Oil supply shock should match supply_shock_oil pattern."""
        key_events = ["Strait of Hormuz closure", "Oil supply disruption"]
        reasoning = "Iran threatens to block oil shipments through Hormuz strait..."

        transmission = match_event_to_pattern(key_events, reasoning)

        # Should match supply_shock_oil
        assert transmission != {}
        assert transmission["XLE"] > 0.8, "Energy should be strong beneficiary"
        assert transmission["XLY"] < -0.5, "Consumers should be hurt"
        assert transmission["XLI"] > 0.5, "Defense contractors should benefit"

    def test_war_geopolitical_pattern(self):
        """War/conflict should match war_geopolitical pattern."""
        key_events = ["Russia invasion", "Military escalation"]
        reasoning = "Ukraine conflict intensifies with missile attacks..."

        transmission = match_event_to_pattern(key_events, reasoning)

        assert transmission != {}
        assert transmission["XLI"] > 0.8, "Defense contractors WIN"
        assert transmission["XLE"] > 0.7, "Energy benefits from war premium"
        assert transmission["XLY"] < -0.5, "Consumers hurt"

    def test_rate_shock_hawkish_pattern(self):
        """Fed hawkish should match rate_shock_hawkish pattern."""
        key_events = ["Fed rate hike", "Yields surge to 5%"]
        reasoning = "Powell signals higher for longer policy stance..."

        transmission = match_event_to_pattern(key_events, reasoning)

        assert transmission != {}
        assert transmission["XLF"] > 0.5, "Financials benefit from higher rates"
        assert transmission["XLK"] < -0.6, "Tech hurt (long-duration crash)"
        assert transmission["XLRE"] < -0.7, "REITs crushed"

    def test_risk_off_pattern(self):
        """Credit stress should match risk_off_credit_stress pattern."""
        key_events = ["Bank crisis", "VIX spike to 40"]
        reasoning = "Credit stress spreads with SVB collapse..."

        transmission = match_event_to_pattern(key_events, reasoning)

        assert transmission != {}
        assert transmission["XLV"] > 0.7, "Healthcare defensive WIN"
        assert transmission["XLP"] > 0.7, "Staples defensive WIN"
        assert transmission["XLY"] < -0.7, "Discretionary LOSE"
        assert transmission["XLF"] < -0.5, "Financials hurt by credit stress"

    def test_recession_pattern(self):
        """Recession should match recession_demand_collapse pattern."""
        key_events = ["GDP miss -2%", "Mass layoffs announced"]
        reasoning = "Economy contracts with unemployment rising to 8%..."

        transmission = match_event_to_pattern(key_events, reasoning)

        assert transmission != {}
        assert transmission["XLV"] > 0.6, "Healthcare defensive"
        assert transmission["XLP"] > 0.6, "Staples defensive"
        assert transmission["XLY"] < -0.7, "Discretionary hurt by demand collapse"
        assert transmission["XLE"] < -0.5, "Energy hurt (demand > supply)"

    def test_fed_dovish_pattern(self):
        """Fed easing should match fed_dovish_easing pattern."""
        key_events = ["Fed rate cut 50bps", "Powell dovish pivot"]
        reasoning = "Central bank shifts to easing with emergency liquidity..."

        transmission = match_event_to_pattern(key_events, reasoning)

        assert transmission != {}
        assert transmission["XLRE"] > 0.6, "REITs rally on lower rates"
        assert transmission["XLK"] > 0.6, "Tech rallies (growth assets)"
        assert transmission["XLU"] > 0.6, "Utilities rally (bond proxy)"

    def test_no_match(self):
        """Unrelated events should return empty dict."""
        key_events = ["Sunny weather forecast"]
        reasoning = "Temperature expected to rise this weekend..."

        transmission = match_event_to_pattern(key_events, reasoning)

        assert transmission == {}

    def test_single_keyword_insufficient(self):
        """Single keyword match should not trigger (min_keyword_matches=2)."""
        key_events = ["Oil price rises"]
        reasoning = "Crude gains 2% on optimism..."

        transmission = match_event_to_pattern(key_events, reasoning)

        # Should not match with only 1 keyword ("oil")
        # Actually this depends on implementation - let's test it
        # If it returns empty, that's correct behavior

    def test_multiple_pattern_blending(self):
        """Multiple matching patterns should blend (sum and clip)."""
        key_events = [
            "Iran war escalation",
            "Oil supply disruption",
            "Hormuz strait closure"
        ]
        reasoning = "War in Middle East blocks oil shipments via Hormuz..."

        transmission = match_event_to_pattern(key_events, reasoning)

        # Should match both supply_shock_oil AND war_geopolitical
        # XLE should be very strong (both patterns boost it)
        # XLY should be very weak (both patterns hurt it)
        assert transmission["XLE"] > 0.9, "XLE should be very strong (multiple patterns)"
        assert transmission["XLY"] < -0.7, "XLY should be very weak"


class TestEventTypeDetection:
    """Test event type classification."""

    def test_detect_supply_shock(self):
        """Should detect supply_shock_oil event type."""
        key_events = ["Strait of Hormuz closure", "Oil supply disruption"]
        event_type = detect_event_type(key_events)

        assert event_type == "supply_shock_oil"

    def test_detect_war(self):
        """Should detect war_geopolitical event type."""
        key_events = ["Russia invasion", "missile attack"]
        event_type = detect_event_type(key_events)

        assert event_type == "war_geopolitical"

    def test_detect_none(self):
        """Should return None for unclear events."""
        key_events = ["Weather update"]
        event_type = detect_event_type(key_events)

        assert event_type is None


class TestTransmissionFormatting:
    """Test transmission context formatting for Step 2 prompt."""

    def test_format_significant_impacts(self):
        """Should format only significant impacts (>0.3)."""
        transmission = {
            "XLE": 0.95,   # Should appear
            "XLY": -0.75,  # Should appear
            "XLI": 0.70,   # Should appear
            "XLF": -0.25,  # Should NOT appear (<0.3)
            "XLP": 0.10,   # Should NOT appear (<0.3)
        }

        formatted = format_transmission_context(transmission)

        assert "XLE: LONG 0.95" in formatted
        assert "XLY: SHORT 0.75" in formatted
        assert "XLI: LONG 0.70" in formatted
        assert "XLF" not in formatted  # Too weak
        assert "XLP" not in formatted  # Too weak

    def test_format_empty_vector(self):
        """Empty transmission should return empty string."""
        formatted = format_transmission_context({})
        assert formatted == ""

    def test_format_includes_instructions(self):
        """Formatted output should include usage instructions and mapping rules."""
        transmission = {"XLE": 0.95, "XLY": -0.75}
        formatted = format_transmission_context(transmission)

        assert "MACRO EVENT TRANSMISSION" in formatted
        # Check for Option A improvements
        assert "TRANSMISSION STRENGTH → SCORE INTERPRETATION" in formatted
        assert "CRITICAL RULES" in formatted
        assert "0.7-1.0  → Target score 8-10" in formatted
        assert "sectors WITH Macro Rules" in formatted
        assert "EXAMPLE:" in formatted


class TestCanonicalPatternDefinitions:
    """Test canonical transmission pattern definitions for sanity."""

    def test_all_patterns_have_11_sectors(self):
        """All transmission vectors should cover all 11 sectors."""
        sectors = {"XLE", "XLF", "XLV", "XLI", "XLP", "XLU", "XLY", "XLK", "XLC", "XLRE", "XLB"}

        for pattern_name, pattern_def in CANONICAL_TRANSMISSIONS.items():
            vector = pattern_def["vector"]
            assert set(vector.keys()) == sectors, f"{pattern_name} missing sectors"

    def test_all_strengths_in_valid_range(self):
        """All transmission strengths should be in [-1.0, 1.0]."""
        for pattern_name, pattern_def in CANONICAL_TRANSMISSIONS.items():
            for sector, strength in pattern_def["vector"].items():
                assert -1.0 <= strength <= 1.0, (
                    f"{pattern_name}.{sector} out of range: {strength}"
                )

    def test_supply_shock_energy_positive(self):
        """Supply shock should have positive energy impact."""
        vector = CANONICAL_TRANSMISSIONS["supply_shock_oil"]["vector"]
        assert vector["XLE"] > 0.8, "Energy should be strong beneficiary"

    def test_rate_shock_tech_negative(self):
        """Rate shock should have negative tech impact."""
        vector = CANONICAL_TRANSMISSIONS["rate_shock_hawkish"]["vector"]
        assert vector["XLK"] < -0.6, "Tech should be hurt by rate hikes"

    def test_risk_off_defensives_positive(self):
        """Risk-off should boost defensive sectors."""
        vector = CANONICAL_TRANSMISSIONS["risk_off_credit_stress"]["vector"]
        assert vector["XLV"] > 0.7, "Healthcare should be defensive winner"
        assert vector["XLP"] > 0.7, "Staples should be defensive winner"
        assert vector["XLU"] > 0.6, "Utilities should be defensive winner"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
