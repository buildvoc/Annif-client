import argparse
import re
import shutil
from pathlib import Path
import dotenv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


from flow_building_wiki import create_building_wiki_flow


def slug(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "page"


def source_slug_from_raw_name(name):
    base = Path(name).name.replace(".annotated.arch_materials.description_classification.json", "")
    return "source-" + slug(base.replace("_", " "))


def prepare_pass1_unprocessed_raw_dir(raw_dir):
    raw_dir = Path(raw_dir)
    wiki_sources = Path("wiki/sources")
    pending_dir = Path("output/pass1_unprocessed_docling_json")

    pending_dir.mkdir(parents=True, exist_ok=True)
    for old in pending_dir.glob("*.json"):
        old.unlink()

    files = sorted(raw_dir.glob("*.json"))
    pending = []

    for src in files:
        source_page = wiki_sources / f"{source_slug_from_raw_name(src.name)}.md"
        if source_page.exists():
            print(f"Pass 1 skip existing source: {src.name}")
            continue
        pending.append(src)
        shutil.copy2(src, pending_dir / src.name)

    print(f"Pass 1 raw files: {len(files)} total, {len(pending)} pending, {len(files) - len(pending)} skipped")

    if not pending:
        raise SystemExit("Pass 1: no new DoclingDocument files to process")

    return str(pending_dir)



def main():
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(description="Create/update Building Memex wiki from DoclingDocument JSON files.")
    parser.add_argument("--raw-dir", default="raw/docling-json")
    parser.add_argument("--schema", default="schema/BUILDING_WIKI.md")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()

    shared = {
        "raw_dir": args.raw_dir,
        "schema_path": args.schema,
        "use_cache": not args.no_cache,
        "limit": args.limit,
        "offset": args.offset,
        "wiki_files_written": [],
    }

    flow = create_building_wiki_flow()
    flow.run(shared)

    import json
    Path("output").mkdir(exist_ok=True)
    Path("output/building_wiki_relationships.json").write_text(
        json.dumps(shared.get("relationships", {}), indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    Path("output/building_wiki_abstractions.json").write_text(
        json.dumps(shared.get("abstractions", []), indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("--- written ---")
    for path in shared.get("wiki_files_written", []):
        print(path)


if __name__ == "__main__":
    main()
