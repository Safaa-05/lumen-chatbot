import pandas as pd

pd.set_option("display.max_colwidth", 100)


def load_split(path):
    """Read one semicolon-separated file into a DataFrame with text and label."""
    return pd.read_csv(path, sep=";", header=None, names=["text", "label"])


train = load_split("data/train.txt")
val = load_split("data/val.txt")
test = load_split("data/test.txt")

print("=== Sizes ===")
print("train:", train.shape, "| val:", val.shape, "| test:", test.shape)

print("\n=== Emotion counts (train) ===")
print(train["label"].value_counts())
print((train["label"].value_counts(normalize=True) * 100).round(1))

print("\n=== Words per text (train) ===")
train["n_words"] = train["text"].str.split().str.len()
print(train["n_words"].describe())

print("\n=== Quality checks ===")
print("Missing values:")
print(train.isna().sum())
print("Duplicate texts in train:", train["text"].duplicated().sum())
print("Texts in both train and test:", len(set(train["text"]) & set(test["text"])))
print("Texts in both train and val:", len(set(train["text"]) & set(val["text"])))

print("\n=== Random examples ===")
print(train[["text", "label"]].sample(5, random_state=1))