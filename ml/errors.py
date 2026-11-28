"""Print real examples the model got wrong, to ground the error analysis.

Run from the project root:  python -m ml.errors
"""
from ml.data import load_clean_splits
from ml.predict import EmotionClassifier

PAIRS = [("joy", "love"), ("love", "joy"), ("sadness", "fear"), ("fear", "sadness"), ("surprise", "joy")]

_, val, _ = load_clean_splits()
model = EmotionClassifier().model

val = val.copy()
val["pred"] = model.predict(val["text"])
wrong = val[val["label"] != val["pred"]]
print(f"{len(wrong)} wrong out of {len(val)} validation texts ({len(wrong) / len(val):.1%})\n")

for true, pred in PAIRS:
    rows = wrong[(wrong["label"] == true) & (wrong["pred"] == pred)]
    print(f"--- true: {true} | predicted: {pred} | {len(rows)} cases ---")
    for text in rows["text"].head(6):
        print("  ", text)
    print()