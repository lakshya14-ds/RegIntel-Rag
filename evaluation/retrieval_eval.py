import json
import os
from typing import List, Dict, Any
from app.retrieval.hybrid import HybridRetriever

class RetrievalEvaluator:
    def __init__(self, questions_path: str = "evaluation/questions.json", retriever: HybridRetriever = None):
        self.questions_path = questions_path
        self.retriever = retriever or HybridRetriever()

    def load_questions(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.questions_path):
            return []
        with open(self.questions_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def evaluate_hit_rate(self, top_k: int = 5) -> float:
        questions = self.load_questions()
        if not questions:
            return 0.0

        hits = 0
        for item in questions:
            query = item["question"]
            expected_keywords = [kw.lower() for kw in item.get("expected_keywords", [])]
            docs = self.retriever.retrieve(query=query, top_k=top_k)
            retrieved_text = " ".join([d.get("text", "").lower() for d in docs])

            if any(kw in retrieved_text for kw in expected_keywords):
                hits += 1

        hit_rate = hits / len(questions)
        print(f"Retrieval Hit Rate@{top_k}: {hit_rate:.2%}")
        return hit_rate

if __name__ == "__main__":
    evaluator = RetrievalEvaluator()
    evaluator.evaluate_hit_rate(top_k=5)
