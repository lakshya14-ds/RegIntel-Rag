import json
import pytest
from pathlib import Path

DATASET_DIR = Path("evaluation/dataset")


def test_retrieval_dataset_structure():
    path = DATASET_DIR / "retrieval_questions.json"
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) >= 40  # Target 40-60
    for item in data:
        assert "id" in item
        assert "question" in item
        assert "expected_documents" in item
        assert "category" in item
        assert len(item["expected_documents"]) > 0


def test_generation_dataset_structure():
    path = DATASET_DIR / "generation_questions.json"
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) >= 25  # Target 25-35
    for item in data:
        assert "id" in item
        assert "question" in item
        assert "answerability" in item
        assert "reference_answer" in item
        assert item["answerability"] in {"ANSWERABLE", "PARTIALLY_ANSWERABLE", "UNANSWERABLE"}


def test_comparison_dataset_structure():
    path = DATASET_DIR / "comparison_cases.json"
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) >= 8  # Target ~10
    for item in data:
        assert "id" in item
        assert "document_a" in item
        assert "document_b" in item
        assert "synthetic_test_case" in item
