import random
import re

LOW_CONFIDENCE = 0.45

# Words for talking about an emotion label naturally ("feeling sad", not "feeling sadness")
ADJECTIVE = {"sadness": "sad", "anger": "angry", "fear": "anxious",
             "joy": "happy", "love": "loving", "surprise": "surprised"}

RESPONSES = {
    "sadness": {
        "support": [
            "I'm sorry you're feeling this way. Your feelings are valid.",
            "That sounds really painful. Thank you for sharing it with me.",
            "It makes sense to feel low after what you've described.",
        ],
        "next": [
            "Do you want to tell me more about what happened?",
            "What's been weighing on you the most today?",
        ],
        "technique": "A small grounding exercise can help: name 5 things you can see, 4 you can touch and 3 you can hear.",
    },
    "anger": {
        "support": [
            "That sounds really frustrating. It's okay to feel angry about it.",
            "It seems like something really got to you. Anger often shows up when something matters.",
        ],
        "next": [
            "What do you think set it off?",
            "What would feel like a fair outcome for you here?",
        ],
        "technique": "Try box breathing: inhale for 4 seconds, hold for 4, exhale for 4, hold for 4. Repeat 4 times.",
    },
    "fear": {
        "support": [
            "Feeling anxious is exhausting, and I'm here with you.",
            "That sounds stressful. Your mind is trying to protect you, even if it feels like too much.",
        ],
        "next": [
            "What's the worry that keeps coming back?",
            "Is there one small thing you could do about it today?",
        ],
        "technique": "Try 4-7-8 breathing: inhale for 4 seconds, hold for 7, exhale slowly for 8. Repeat 3 times.",
    },
    "joy": {
        "support": [
            "That's wonderful to hear! I'm really glad you're feeling good.",
            "It's great that you're feeling positive. You deserve moments like this.",
        ],
        "next": [
            "What do you think contributed to this feeling?",
            "Want to tell me more about what made it good?",
        ],
        "technique": None,
    },
    "love": {
        "support": [
            "It's lovely that you're feeling connected and warm.",
            "Those bonds matter a lot, and it sounds like they matter to you.",
        ],
        "next": [
            "Who or what is making you feel this way?",
            "Is there something you'd like to tell that person?",
        ],
        "technique": None,
    },
    "surprise": {
        "support": [
            "That sounds unexpected! It can take a moment to take it in.",
            "Wow, that must have caught you off guard.",
        ],
        "next": [
            "How are you feeling about it now?",
            "Is it a good surprise or a difficult one?",
        ],
        "technique": None,
    },
}

NEGATIVE = {"sadness", "anger", "fear"}
POSITIVE = {"joy", "love"}

CLARIFY = [
    "I'm not completely sure I understood. Could you tell me a bit more about how you're feeling?",
    "I want to get this right. Can you describe what's going on in a few more words?",
]

SMALL_TALK = {
    "bye": ({"bye", "goodbye", "see", "you", "later", "good", "night"},
            "Take care of yourself. I'm here whenever you want to talk again."),
    "thanks": ({"thanks", "thank", "you", "so", "much", "a", "lot", "thx"},
               "You're welcome. I'm glad I could help. How are you feeling now?"),
    "greeting": ({"hi", "hello", "hey", "hii", "there", "good", "morning", "afternoon", "evening"},
                 "Hi, I'm here to listen. How are you feeling today?"),
}


def small_talk_reply(text):
    """Reply to a pure greeting, thanks or goodbye. Returns None for anything else."""
    words = set(re.findall(r"[a-z']+", text.lower()))
    if not words:
        return None
    for allowed, reply in SMALL_TALK.values():
        if words <= allowed:
            return reply
    return None


def memory_line(emotion, history):
    """A short line that uses what the person said earlier, or None."""
    if not history:
        return None
    prev = history[-1]
    if prev in NEGATIVE and emotion in POSITIVE:
        return f"It's good to hear something lighter after you felt {ADJECTIVE[prev]} earlier."
    if prev == emotion and emotion in NEGATIVE:
        return f"You've been feeling {ADJECTIVE[emotion]} for a little while now, and I'm sorry it's lasting."
    return None


def build_reply(emotion, intensity, history, confidence, risk="none"):
    """Choose a reply from emotion, intensity, earlier emotions, confidence and risk."""
    if confidence < LOW_CONFIDENCE:
        return random.choice(CLARIFY)

    bank = RESPONSES[emotion]
    support = random.choice(bank["support"])
    if intensity >= 0.7:
        support = "I can hear how intense this is. " + support
    parts = [support]

    # When risk is moderate, keep the reply short and calm: support plus one question
    if risk == "moderate":
        parts.append(random.choice(bank["next"]))
        return " ".join(parts)

    memory = memory_line(emotion, history)
    parts.append(memory or random.choice(bank["next"]))

    repeating = bool(history) and history[-1] == emotion
    if repeating and memory:
        # The same feeling again: ask a question instead of repeating the technique
        parts.append(random.choice(bank["next"]))
    elif emotion in NEGATIVE and intensity >= 0.4 and bank["technique"]:
        parts.append(bank["technique"])

    return " ".join(parts)