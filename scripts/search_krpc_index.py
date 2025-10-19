import argparse
import sys
from pathlib import Path

# Ensure project root (parent of scripts/) is on sys.path for local imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from krpc_index import KRPCSearchIndex, load_dataset


def main() -> int:
    ap = argparse.ArgumentParser(description="Search the kRPC docs dataset")
    ap.add_argument("query", nargs="+", help="Search terms")
    ap.add_argument("--data", default="data/krpc_python_docs.jsonl", help="Path to JSONL dataset")
    ap.add_argument("--k", type=int, default=10, help="Top K results")
    args = ap.parse_args()

    docs = load_dataset(Path(args.data))
    idx = KRPCSearchIndex(docs)

    q = " ".join(args.query)
    results = idx.search(q, top_k=args.k)
    for i, (doc, score, snippet) in enumerate(results, start=1):
        print(f"{i}. {doc.title} — {doc.url} (score={score:.2f})")
        if snippet:
            print(f"   {snippet}")
    if not results:
        print("No results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
