import re

# Explicit self-harm / suicide language -> always treated as high risk
HIGH_RISK_PATTERNS = [
    r"\bkill (myself|my self)\b",
    r"\bsuicid(e|al)\b",
    r"\bend (my life|it all)\b",
    r"\bwant(ed)? to die\b",
    r"\bwish i (was|were) dead\b",
    r"\bdon'?t want to (live|be alive|exist)\b",
    r"\bno reason to live\b",
    r"\b(hurt|harm|cut) myself\b",
    r"\bself[- ]?harm\b",
    r"\bbetter off (dead|without me)\b",
    r"\btake my (own )?life\b",
    r"\bcan'?t go on\b",
]

# Softer signs of deep distress; two or more together -> moderate risk
DISTRESS_CUES = [
    "hopeless", "worthless", "no point", "give up", "nobody cares",
    "burden", "empty", "trapped", "unbearable", "can't take", "cannot take",
]

HELPLINES = [
    {"name": "Tele-MANAS (24x7, free)", "contact": "14416"},
    {"name": "KIRAN Mental Health Helpline", "contact": "1800-599-0019"},
    {"name": "Emergency services", "contact": "112"},
]

CRISIS_MESSAGE = (
    "I'm really glad you told me, and I'm concerned about you. You don't have "
    "to face this alone. If you are in immediate danger, please call 112. "
    "Talking to a trained counsellor can help, and the helplines below are "
    "free. Is there someone you trust who could be with you right now?"
)

MODERATE_NOTE = (
    "It sounds like things feel really heavy right now. If it ever feels like "
    "too much, Tele-MANAS (14416) is available 24x7."
    
)

_HIGH = [re.compile(p, re.IGNORECASE) for p in HIGH_RISK_PATTERNS]


def assess_risk(text):
    """Return 'high', 'moderate' or 'none' for a message."""
    if any(p.search(text) for p in _HIGH):
        return "high"
    lowered = text.lower()
    hits = [cue for cue in DISTRESS_CUES if cue in lowered]
    if len(hits) >= 2:
        return "moderate"
    return "none"