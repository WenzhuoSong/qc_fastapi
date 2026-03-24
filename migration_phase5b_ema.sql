-- Phase 5b P0 Optimization: Add EMA smoothing fields to DecisionLog
-- Date: 2026-03-24
-- Purpose: Reduce random noise from single-day LLM variance

-- Add Phase 5b contradiction tracking fields
ALTER TABLE decision_log
ADD COLUMN IF NOT EXISTS contradiction_score_raw FLOAT,
ADD COLUMN IF NOT EXISTS contradiction_score_ema3 FLOAT,
ADD COLUMN IF NOT EXISTS llm_confidence_adjustment INTEGER;

-- Comments for documentation
COMMENT ON COLUMN decision_log.contradiction_score_raw IS
  'Phase 5b: Raw LLM contradiction score from current day (0.0-1.0)';

COMMENT ON COLUMN decision_log.contradiction_score_ema3 IS
  'Phase 5b: 3-day EMA smoothed contradiction score (reduces noise, used for trigger logic)';

COMMENT ON COLUMN decision_log.llm_confidence_adjustment IS
  'Phase 5b: LLM suggested confidence adjustment (-50 to +20)';
