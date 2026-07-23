import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.reid import match_person, register_person


def test_register_then_match_same_embedding():
    embedding = [1.0, 0.0, 0.0, 0.0]
    person_id = register_person(embedding)

    matched = match_person(embedding, threshold=0.9)

    assert matched == person_id


def test_match_returns_none_for_unrelated_embedding():
    register_person([1.0, 0.0, 0.0, 0.0])

    matched = match_person([0.0, 1.0, 0.0, 0.0], threshold=0.9)

    assert matched is None


if __name__ == "__main__":
    test_register_then_match_same_embedding()
    test_match_returns_none_for_unrelated_embedding()
    print("OK")
