"""Versioned ranking policy. Thresholds are heuristics, not probabilities."""

WEIGHTS = {
    "relevance": 0.60,
    "industry": 0.11,
    "stage": 0.08,
    "experience": 0.06,
    "format": 0.09,
    "urgency": 0.06,
    "feedback": 0.05,
}
SEMANTIC_CONFIG = {
    "floor": 0.81,
    "margin": 0.008,
    "lexical_evidence": 0.10,
    "offset": 0.65,
    "span": 0.35,
    "weight": 0.4,
    "unknown_floor": 0.84,
    "unknown_word_floor": 0.05,
}
PERSONAL_VERSION = "personal-v5"
BASELINE_VERSION = "topic-baseline-v3"
MIN_RELEVANCE = 0.075
GENERAL_LIMIT = 3
CONSTRAINT_LIMIT = 3
GENERAL_RELATIVE_FLOOR = 0.75
DIVERSITY_PENALTY = 0.035
