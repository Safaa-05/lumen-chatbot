import pickle


class EmotionClassifier:
    def __init__(self, path="models/emotion_model.pkl"):
        with open(path, "rb") as f:
            bundle = pickle.load(f)
        self.model = bundle["model"]
        self.name = bundle["name"]

    def predict(self, text):
        probs = self.model.predict_proba([text])[0]
        classes = self.model.classes_
        order = probs.argsort()[::-1]
        return {
            "emotion": str(classes[order[0]]),
            "confidence": round(float(probs[order[0]]), 3),
            "top": [{"emotion": str(classes[i]), "score": round(float(probs[i]), 3)}
                    for i in order[:3]],
        }