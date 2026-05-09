import argparse
import dotenv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


from flow_building_wiki import create_building_wiki_flow


def main():
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(description="Create/update Building Memex wiki from DoclingDocument JSON files.")
    parser.add_argument("--raw-dir", default="raw/docling-json")
    parser.add_argument("--schema", default="schema/BUILDING_WIKI.md")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    shared = {
        "raw_dir": args.raw_dir,
        "schema_path": args.schema,
        "use_cache": not args.no_cache,
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
