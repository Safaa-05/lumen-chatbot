import pandas as pd


def load_split(path):
    """Read one semicolon-separated file into a DataFrame with text and label."""
    return pd.read_csv(path, sep=";", header=None, names=["text", "label"])


def load_clean_splits():
    """Load train/val/test, then remove duplicates and train/val/test overlap."""
    train = load_split("data/train.txt")
    val = load_split("data/val.txt")
    test = load_split("data/test.txt")

    train = train.drop_duplicates(subset="text")
    train_texts = set(train["text"])
    val = val[~val["text"].isin(train_texts)]
    test = test[~test["text"].isin(train_texts)]
    return train, val, test