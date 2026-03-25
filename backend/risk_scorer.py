# ──────────────────────────────────────────────────────────────
# PLACEHOLDER — Member 1 will replace this with the real
# spaCy + BERT NLP implementation.
#
# This stub lets Member 2's API run and be tested by the
# frontend team immediately without waiting.
# ──────────────────────────────────────────────────────────────

DRUG_SLANG_KEYWORDS = [
    "snow", "white girl", "molly", "ice", "crystal", "boy",
    "girl", "h", "smack", "crack", "rock", "plug", "pack",
    "drop", "fire", "loud", "weed", "bud", "420", "dope",
]

def score_message(text: str) -> dict:
    """
    Placeholder NLP scorer.
    Checks for known drug slang keywords and assigns a base score.

    Member 1 will replace this with spaCy + BERT for real inference.
    """
    text_lower = text.lower()
    found_keywords = [kw for kw in DRUG_SLANG_KEYWORDS if kw in text_lower]

    # Each keyword hit adds 15 points, capped at 60
    score = min(len(found_keywords) * 15, 60)
    flags = ["drug_slang"] if found_keywords else []

    return {
        "score": float(score),
        "flags": flags,
        "matched_keywords": found_keywords
    }
