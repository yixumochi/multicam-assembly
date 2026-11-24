"""Portable, read-only entry point for the MultiCam text retrieval snapshot."""
import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(os.environ.get(
    "MULTICAM_BASELINE_ROOT", Path(__file__).resolve().parent / "data" / "baseline"
)).expanduser().resolve()
CACHE = ROOT / "work/semantic_run"
MODEL = Path(os.environ.get(
    "MULTICAM_SBERT_MODEL", ROOT / "legacy_source_reuse/text/models/all-MiniLM-L6-v2"
)).expanduser().resolve()
ROUND2 = ROOT / "outputs/action_comparison_round2"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def encode(texts):
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(4)
    encoder = SentenceTransformer(str(MODEL), device="cpu", local_files_only=True)
    return encoder.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def audit():
    from sklearn.cluster import AgglomerativeClustering

    labels = read(CACHE / "labels.json")
    similarity = np.load(CACHE / "cosine_similarity.npy")
    distance = np.maximum(0, 1 - similarity)
    np.fill_diagonal(distance, 0)
    fitted = AgglomerativeClustering(
        n_clusters=None, metric="precomputed", linkage="complete",
        distance_threshold=1 - 0.65,
    ).fit_predict(distance)
    clusters = defaultdict(list)
    for label, cluster in zip(labels, fitted):
        clusters[int(cluster)].append(label)
    original = read(ROOT / "outputs/semantic_action_groups.json")["clusters"]
    assert {frozenset(c) for c in clusters.values()} == {
        frozenset(c["labels"]) for c in original
    }
    return {"labels": len(labels), "groups": len(clusters), "members_match": True}


def encode_check():
    current = encode(read(CACHE / "labels.json"))
    original = np.load(CACHE / "label_embeddings.npy")
    np.testing.assert_allclose(current, original, rtol=1e-4, atol=1e-5)
    return {"shape": list(current.shape), "max_abs_diff": float(np.max(np.abs(current - original)))}


def search(query, top_k):
    expressions = read(ROOT / "outputs/research_state/expressions.json")
    by_id = {event["id"]: index for index, event in enumerate(read(ROUND2 / "events.json"))}
    matrix = np.load(ROUND2 / "event_text_embeddings.npy")
    if len(matrix) != len(by_id):
        raise ValueError("Event and embedding counts disagree")
    query_vector = encode([query])[0]
    scores = matrix @ query_vector
    results = []
    for expression in expressions:
        ids = expression["event_ids"]
        score = float(scores[by_id[ids[0]]])
        results.append({"text": expression["text"], "cosine": score,
                        "cases": expression["cases"], "event_ids": ids})
    return sorted(results, key=lambda row: (-row["cosine"], row["text"]))[:top_k]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("audit")
    subcommands.add_parser("encode-check")
    query_parser = subcommands.add_parser("search")
    query_parser.add_argument("query")
    query_parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    if args.command == "audit":
        result = audit()
    elif args.command == "encode-check":
        result = encode_check()
    else:
        if args.top_k < 1:
            query_parser.error("--top-k must be positive")
        result = search(args.query, args.top_k)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
