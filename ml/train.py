import json
import os
import pickle

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score)
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from ml.data import load_clean_splits

train, val, test = load_clean_splits()


def make_pipeline(clf):
    tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    return Pipeline([("tfidf", tfidf), ("clf", clf)])


candidates = {
    "Complement NB": make_pipeline(ComplementNB(alpha=0.3)),
    "LogReg C=1": make_pipeline(LogisticRegression(C=1, max_iter=1000, class_weight="balanced")),
    "LogReg C=5": make_pipeline(LogisticRegression(C=5, max_iter=1000, class_weight="balanced")),
    "LogReg C=20": make_pipeline(LogisticRegression(C=20, max_iter=1000, class_weight="balanced")),
    # LinearSVC has no probabilities, so wrap it to get confidence scores
    "Linear SVM": make_pipeline(CalibratedClassifierCV(LinearSVC(class_weight="balanced"), cv=3)),
}

# 1) Compare every model on the VALIDATION set
results = {}
fitted = {}
for name, pipe in candidates.items():
    pipe.fit(train["text"], train["label"])
    pred = pipe.predict(val["text"])
    results[name] = {
        "val_accuracy": round(accuracy_score(val["label"], pred), 4),
        "val_macro_f1": round(f1_score(val["label"], pred, average="macro"), 4),
    }
    fitted[name] = pipe
    print(f"{name:15s} acc={results[name]['val_accuracy']}  macro-F1={results[name]['val_macro_f1']}")

best_name = max(results, key=lambda n: results[n]["val_macro_f1"])
best = fitted[best_name]
print("\nBest model on validation:", best_name)

# 2) Confusion matrix on validation (for error analysis)
labels = sorted(train["label"].unique())
val_pred = best.predict(val["text"])
cm = confusion_matrix(val["label"], val_pred, labels=labels)

fig, ax = plt.subplots(figsize=(6, 5))
ax.imshow(cm, cmap="Blues")
ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
ax.set_yticks(range(len(labels)), labels)
for i in range(len(labels)):
    for j in range(len(labels)):
        ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=9)
ax.set_xlabel("Predicted")
ax.set_ylabel("True")
ax.set_title(f"Confusion matrix (validation): {best_name}")
plt.tight_layout()
os.makedirs("models", exist_ok=True)
plt.savefig("models/confusion_matrix.png", dpi=150)

# 3) Final score on the TEST set, used exactly once
test_pred = best.predict(test["text"])
test_acc = round(accuracy_score(test["label"], test_pred), 4)
test_f1 = round(f1_score(test["label"], test_pred, average="macro"), 4)
print(f"\nTEST accuracy={test_acc}  macro-F1={test_f1}")
print(classification_report(test["label"], test_pred))

# 4) Save the model and the numbers
with open("models/emotion_model.pkl", "wb") as f:
    pickle.dump({"model": best, "name": best_name, "labels": labels}, f)

with open("models/metrics.json", "w") as f:
    json.dump({"best": best_name, "validation": results,
               "test": {"accuracy": test_acc, "macro_f1": test_f1}}, f, indent=2)

print("Saved models/emotion_model.pkl, metrics.json and confusion_matrix.png")