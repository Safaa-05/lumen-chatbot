import random
import re

from core.intensity import intensity_label, intensity_score
from core.responses import CLARIFY, LOW_CONFIDENCE, build_reply, small_talk_reply
from core.safety import CRISIS_MESSAGE, HELPLINES, MODERATE_NOTE, assess_risk

FIRST_PERSON = {"i", "im", "i'm", "i've", "ive", "i'll", "me", "my", "myself", "mine", "we", "our", "us"}
SURE_ENOUGH = 0.8  # above this, trust the model even without a first-person word


def is_personal(text):
    """True if the text talks about the speaker (I, me, my...)."""
    return bool(set(re.findall(r"[a-z']+", text.lower())) & FIRST_PERSON)


def _result(reply, emotion=None, confidence=None, intensity=0.0, risk="none", helplines=None):
    return {"reply": reply, "emotion": emotion, "confidence": confidence,
            "intensity": intensity, "intensity_label": intensity_label(intensity),
            "risk": risk, "helplines": helplines}


def respond(text, classifier, history):
    """Return a dict with the reply and details. `history` is a list of earlier emotions
    and gets updated in place."""
    # 1) Safety check always runs first and overrides everything
    risk = assess_risk(text)
    if risk == "high":
        return _result(CRISIS_MESSAGE, intensity=1.0, risk="high", helplines=HELPLINES)

    # 2) Plain greetings, thanks and goodbyes don't need the model
    small = small_talk_reply(text)
    if small:
        return _result(small)

    # 3) Emotion and intensity
    pred = classifier.predict(text)
    intensity = intensity_score(text)

    # 4) Out-of-scope guard: the model has no "neutral" class, so it forces an emotion
    #    onto things like "what time is it". If the text isn't about the speaker and the
    #    model isn't very sure, ask for more instead of guessing.
    if not is_personal(text) and pred["confidence"] < SURE_ENOUGH:
        return _result(random.choice(CLARIFY), confidence=pred["confidence"])

    reply = build_reply(pred["emotion"], intensity, history, pred["confidence"], risk)

    helplines = None
    if risk == "moderate":
        reply += " " + MODERATE_NOTE
        helplines = HELPLINES

    # 5) Remember the emotion only when the model was reasonably sure
    if pred["confidence"] >= LOW_CONFIDENCE:
        history.append(pred["emotion"])
        del history[:-6]

    return _result(reply, pred["emotion"], pred["confidence"], intensity, risk, helplines)