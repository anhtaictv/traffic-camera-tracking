import numpy as np

# ponytail: lưu embedding trong RAM (mất khi restart process) -> nâng cấp lên
# bảng DB (storage.py) khi cần persist qua nhiều phiên chạy.
_person_embeddings: dict[int, list[np.ndarray]] = {}
_next_person_id = 1


def _average_embedding(embeddings: list[np.ndarray]) -> np.ndarray:
    return np.mean(embeddings[-10:], axis=0)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def match_person(embedding: list[float], threshold: float = 0.7) -> int | None:
    """Tìm global person_id có embedding lưu sẵn gần nhất, None nếu không đạt threshold."""
    query = np.array(embedding)
    best_id, best_sim = None, -1.0
    for person_id, embeddings in _person_embeddings.items():
        sim = _cosine_similarity(query, _average_embedding(embeddings))
        if sim > best_sim:
            best_id, best_sim = person_id, sim

    if best_id is not None and best_sim >= threshold:
        _person_embeddings[best_id].append(query)
        return best_id
    return None


def register_person(embedding: list[float]) -> int:
    """Tạo global person_id mới cho embedding chưa match."""
    global _next_person_id
    person_id = _next_person_id
    _next_person_id += 1
    _person_embeddings[person_id] = [np.array(embedding)]
    return person_id
