import json
import os
from typing import List, Dict, Any
from openai import OpenAI
from app.config import settings
from app.rag.pipeline import RAGPipeline

class GenerationEvaluator:
    def __init__(self, questions_path: str = "evaluation/questions.json", pipeline: RAGPipeline = None):
        self.questions_path = questions_path
        self.pipeline = pipeline or RAGPipeline()
        self.client = OpenAI(api_key=settings.openai_api_key)

    def load_questions(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.questions_path):
            return []
        with open(self.questions_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def judge_answer(self, question: str, generated_answer: str, ground_truth: str) -> float:
        prompt = f"""You are an impartial evaluator for a regulatory AI assistant.
Evaluate how accurately and completely the generated answer addresses the question relative to the ground truth.
Assign a score from 0.0 to 1.0, where 1.0 is completely faithful and correct, and 0.0 is incorrect or irrelevant.
Output ONLY the numeric score (e.g., 0.85).

Question: {question}
Ground Truth: {ground_truth}
Generated Answer: {generated_answer}
Score:"""
        try:
            response = self.client.chat.completions.create(
                model=settings.llm_model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            score_text = response.choices[0].message.content.strip()
            return float(score_text)
        except Exception:
            return 0.0

    def run_evaluation(self) -> Dict[str, Any]:
        questions = self.load_questions()
        if not questions:
            return {"average_score": 0.0, "details": []}

        scores = []
        details = []
        for item in questions:
            q = item["question"]
            gt = item.get("ground_truth", "")
            rag_output = self.pipeline.run(query=q)
            ans = rag_output.get("answer", "")
            score = self.judge_answer(question=q, generated_answer=ans, ground_truth=gt)
            scores.append(score)
            details.append({"id": item.get("id"), "question": q, "score": score, "answer": ans})

        avg_score = sum(scores) / len(scores) if scores else 0.0
        print(f"Average Generation Quality Score: {avg_score:.2f}")
        return {"average_score": avg_score, "details": details}

if __name__ == "__main__":
    evaluator = GenerationEvaluator()
    evaluator.run_evaluation()
