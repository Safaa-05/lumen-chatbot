import re

BOOSTERS = {"very", "so", "extremely", "really", "totally", "completely",
            "absolutely", "constantly", "always", "never", "terribly", "utterly"}
DAMPENERS = {"slightly", "bit", "little", "somewhat", "kinda", "mildly", "okay", "fine"}
STRONG = {"cannot", "can't", "hate", "terrified", "devastated", "furious",
          "panic", "exhausted", "worst", "unbearable", "overwhelmed", "hopeless"}


def intensity_score(text):
    """Rough 0-1 score of how strongly the person expresses the feeling."""
    words = re.findall(r"[a-z']+", text.lower())
    if not words:
        return 0.0
    score = 0.4
    score += 0.12 * sum(w in BOOSTERS for w in words)
    score += 0.18 * sum(w in STRONG for w in words)
    score -= 0.12 * sum(w in DAMPENERS for w in words)
    score += 0.08 * min(text.count("!"), 3)
    shouting = sum(1 for w in text.split() if len(w) > 2 and w.isupper())
    score += 0.10 * min(shouting, 2)
    return round(max(0.0, min(1.0, score)), 2)


def intensity_label(score):
    if score < 0.4:
        return "low"
    if score < 0.7:
        return "medium"
    return "high"