from core.intensity import intensity_score
from core.safety import assess_risk


def test_high_risk_is_detected():
    for text in ["I want to die", "I'm thinking about suicide",
                 "i want to kill myself", "I can't go on"]:
        assert assess_risk(text) == "high", text


def test_normal_text_is_not_flagged():
    for text in ["I'm stressed about my exam", "I killed it in my presentation",
                 "I had a great day"]:
        assert assess_risk(text) == "none", text


def test_two_distress_cues_are_moderate():
    assert assess_risk("I feel hopeless and worthless") == "moderate"


def test_intensity_ordering():
    mild = intensity_score("I'm a bit stressed")
    severe = intensity_score("I am EXTREMELY overwhelmed and I cannot take this!!")
    assert severe > mild