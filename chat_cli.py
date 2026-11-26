from core.engine import respond
from ml.predict import EmotionClassifier

classifier = EmotionClassifier()
history = []

print("Type 'quit' to exit.\n")
while True:
    text = input("You: ").strip()
    if text.lower() in {"quit", "exit"}:
        break
    if not text:
        continue
    result = respond(text, classifier, history)
    print("Bot:", result["reply"])
    if result["helplines"]:
        for h in result["helplines"]:
            print("    -", h["name"], h["contact"])
    print(f"    [emotion={result['emotion']} confidence={result['confidence']} "
          f"intensity={result['intensity']} risk={result['risk']}]\n")