import argparse
import json
from pathlib import Path


def should_keep(url: str) -> bool:
    """Return True if the URL should be kept in the filtered dataset.

    Rules:
    - Keep Python pages (contain '/python')
    - Keep Welcome/root index page
    - Keep Getting Started
    - Keep Tutorials index and all tutorials subpages
    """
    if "/python" in url:
        return True
    if url.rstrip("/") == "https://krpc.github.io/krpc":
        return True
    if "getting-started" in url:
        return True
    if "/tutorial" in url:
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Filter JSONL dataset to Python-only docs")
    ap.add_argument("--infile", default="data/krpc_python_docs.jsonl")
    ap.add_argument("--outfile", default="data/krpc_python_docs.jsonl")
    ap.add_argument("--backup", default="data/krpc_python_docs.full.jsonl")
    args = ap.parse_args()

    in_path = Path(args.infile)
    out_path = Path(args.outfile)
    backup_path = Path(args.backup)

    # Backup
    if backup_path.resolve() != in_path.resolve():
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(in_path.read_text(encoding="utf-8"), encoding="utf-8")

    kept = 0
    total = 0
    out_lines = []
    with in_path.open("r", encoding="utf-8") as f:
        for line in f:
            total += 1
            line = line.rstrip("\n")
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = obj.get("url", "")
            if should_keep(url):
                out_lines.append(json.dumps(obj, ensure_ascii=False))
                kept += 1

    out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(json.dumps({"filtered_total": total, "kept": kept, "outfile": str(out_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
