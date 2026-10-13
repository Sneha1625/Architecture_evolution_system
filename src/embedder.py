"""
embedder.py — Semantic Code Embedding & Similarity Engine
VTU Major Project: AI-Driven Semantic Code Analysis and Automated Software Architecture Modeling System
"""

from sentence_transformers import SentenceTransformer
import json
import math

# Load model once (downloads ~80MB on first run)
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parent.parent / "local_model"

model = SentenceTransformer(
    str(MODEL_PATH),
    local_files_only=True
)


def get_code_embedding(text):
    """Generate a semantic embedding vector for a code snippet or description."""
    embedding = model.encode(text)
    return embedding.tolist()


def embed_parsed_result(parsed_result):
    """
    Generate embeddings for all functions and classes in a parsed file.
    Uses richer text descriptions including docstrings and args for better semantics.
    """
    embeddings = []

    for func in parsed_result.get("functions", []):
        args_str = ", ".join(
            a["name"] + (f": {a['type']}" if a.get("type") else "")
            for a in func.get("args", [])
        )
        docstring = func.get("docstring", "")
        text = (
            f"Python function {func['name']} "
            f"with parameters ({args_str}). "
            f"{docstring} "
            f"Complexity: {func.get('complexity_label', 'low')}."
        ).strip()

        embeddings.append({
            "type": "function",
            "name": func["name"],
            "line": func["line"],
            "text": text,
            "embedding": get_code_embedding(text)
        })

    for cls in parsed_result.get("classes", []):
        methods_str = ", ".join(m["name"] for m in cls.get("methods", []))
        docstring = cls.get("docstring", "")
        text = (
            f"Python class {cls['name']} "
            f"with methods: {methods_str}. "
            f"{docstring}"
        ).strip()

        embeddings.append({
            "type": "class",
            "name": cls["name"],
            "line": cls["line"],
            "text": text,
            "embedding": get_code_embedding(text)
        })

    return embeddings


def cosine_similarity(vec1, vec2):
    """Compute cosine similarity between two embedding vectors."""
    dot = sum(a * b for a, b in zip(vec1, vec2))
    mag1 = math.sqrt(sum(a ** 2 for a in vec1))
    mag2 = math.sqrt(sum(b ** 2 for b in vec2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


def find_similar(query_text, embeddings, top_k=3):
    """
    Find the top-k most semantically similar functions/classes to a query.
    Useful for 'find functions similar to X' feature.
    """
    query_vec = get_code_embedding(query_text)
    scores = []
    for item in embeddings:
        sim = cosine_similarity(query_vec, item["embedding"])
        scores.append({
            "name": item["name"],
            "type": item["type"],
            "line": item["line"],
            "similarity": round(sim, 4),
            "text": item.get("text", "")
        })
    scores.sort(key=lambda x: x["similarity"], reverse=True)
    return scores[:top_k]


def build_similarity_matrix(embeddings):
    """
    Build a pairwise similarity matrix for all embeddings.
    Returns list of (name_a, name_b, similarity) tuples sorted by similarity.
    """
    pairs = []
    n = len(embeddings)
    for i in range(n):
        for j in range(i + 1, n):
            sim = cosine_similarity(
                embeddings[i]["embedding"],
                embeddings[j]["embedding"]
            )
            pairs.append({
                "a": embeddings[i]["name"],
                "b": embeddings[j]["name"],
                "similarity": round(sim, 4)
            })
    pairs.sort(key=lambda x: x["similarity"], reverse=True)
    return pairs


if __name__ == "__main__":
    from parser import parse_file

    parsed = parse_file("../samples/sample.py")
    embeddings = embed_parsed_result(parsed)

    print("=== Embeddings ===")
    for item in embeddings:
        print(f"{item['type']:10} | {item['name']:25} | vec len: {len(item['embedding'])}")
        print(f"           | text: {item['text'][:60]}...")

    if len(embeddings) >= 2:
        print("\n=== Similarity Matrix ===")
        matrix = build_similarity_matrix(embeddings)
        for pair in matrix:
            print(f"  {pair['a']} <-> {pair['b']}: {pair['similarity']:.4f}")

        print("\n=== Semantic Search ===")
        results = find_similar("load data from file", embeddings, top_k=3)
        for r in results:
            print(f"  [{r['similarity']:.4f}] {r['type']} {r['name']} (line {r['line']})")