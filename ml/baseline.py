from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.pipeline import Pipeline

from ml.data import load_clean_splits

train, val, test = load_clean_splits()
print("train:", len(train), "| val:", len(val), "| test:", len(test))

pipe = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
    ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
])

pipe.fit(train["text"], train["label"])
pred = pipe.predict(val["text"])

print("\nValidation accuracy:", round(accuracy_score(val["label"], pred), 3))
print("Validation macro-F1:", round(f1_score(val["label"], pred, average="macro"), 3))
print()
print(classification_report(val["label"], pred))