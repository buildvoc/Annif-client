#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path

def run(cmd):
    print("\nRUN:", " ".join(cmd), flush=True)
    return subprocess.run(cmd)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="/app/raw/docling-json")
    ap.add_argument("--schema", default="/app/schema/BUILDING_WIKI.md")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--total", type=int, default=None)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--continue-on-error", action="store_true")
    args = ap.parse_args()

    if args.total is None:
        raw_for_count = args.raw_dir
        if raw_for_count.startswith("/app/"):
            raw_for_count = raw_for_count.replace("/app/", "", 1)
        args.total = len(list(Path(raw_for_count).glob("*.json")))
        print("batch raw-dir:", raw_for_count)
        print("batch total:", args.total)

    failed = []

    for offset in range(args.start, args.total, args.batch_size):
        limit = min(args.batch_size, args.total - offset)
        inner = (
            "cd /app && "
            "PYTHONDONTWRITEBYTECODE=1 python scripts/llm_02_pass_ingest_building_wiki.py "
            f"--raw-dir {args.raw_dir} "
            f"--schema {args.schema} "
            f"--offset {offset} "
            f"--limit {limit} "
            + ("--no-cache" if args.no_cache else "")
        )

        cmd = ["docker-compose", "exec", "-T", "tutorial-generator", "bash", "-lc", inner]
        res = run(cmd)

        if res.returncode != 0:
            failed.append({"offset": offset, "limit": limit, "returncode": res.returncode})
            if not args.continue_on_error:
                break

    Path("output").mkdir(exist_ok=True)
    Path("output/batch_failures.txt").write_text(
        "\n".join(str(x) for x in failed) + ("\n" if failed else ""),
        encoding="utf-8",
    )

    print("\nBatches complete")
    print("failed:", len(failed))
    for f in failed:
        print(f)

    return 1 if failed and not args.continue_on_error else 0

if __name__ == "__main__":
    raise SystemExit(main())
