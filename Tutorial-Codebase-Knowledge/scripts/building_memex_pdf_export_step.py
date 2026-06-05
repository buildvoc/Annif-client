#!/usr/bin/env python3
from pathlib import Path
from datetime import date
import argparse
import json
import re

RAW = Path("raw/docling-json")
WIKI = Path("wiki")

def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def title_of(path):
    if not path.exists():
        return path.stem
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ").title()

def source_slug(path):
    name = path.name
    name = name.replace(".annotated.arch_materials.description_classification.json", "")
    name = name.replace(".json", "")
    return "source-" + slugify(name)

def find_building(place):
    if not place:
        return None

    target = slugify(place)
    buildings = list((WIKI / "buildings").glob("*.md"))

    for p in buildings:
        if target in p.stem or p.stem in target:
            return p

    for p in buildings:
        t = slugify(title_of(p))
        if target in t or t in target:
            return p

    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default="PDF_EXPORT*.json")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = sorted(RAW.glob(args.pattern))
    (WIKI / "sources").mkdir(parents=True, exist_ok=True)

    processed = 0
    skipped = 0
    linked = 0

    for raw in files:
        s_slug = source_slug(raw)
        s_path = WIKI / "sources" / f"{s_slug}.md"

        if s_path.exists() and not args.force:
            print("skip already processed:", raw.name)
            skipped += 1
            continue

        try:
            data = json.loads(raw.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            print("skip unreadable:", raw.name, e)
            continue

        pictures = data.get("pictures", [])
        if not pictures:
            print("skip no pictures:", raw.name)
            continue

        pic = pictures[0]
        meta = pic.get("meta", {}) or {}
        prov = (pic.get("prov") or [{}])[0]
        bbox = prov.get("bbox", {})

        place = meta.get("place", "")
        material = meta.get("materials_context", "")
        classification = meta.get("picture_classification", "")

        related_building = find_building(place)
        related_slug = related_building.stem if related_building else ""
        related = f"- [[{related_slug}]]\n" if related_slug else "- No matched building page yet.\n"

        print("process new:", raw.name)
        if args.dry_run:
            processed += 1
            continue

        s_path.write_text(f"""# Source: {raw.stem.replace("_", " ")}

**Raw file**: `{raw}`  
**Status**: processed PDF_EXPORT picture evidence  
**Processed at**: {date.today().isoformat()}

## Picture metadata

- Place: `{place}`
- Materials context: `{material}`
- Picture classification: `{classification}`
- Page: `{prov.get("page_no", "")}`
- Bounding box: `{bbox}`

## Related pages

{related}
""", encoding="utf-8")
        processed += 1
        print("wrote", s_path)

        if related_building:
            text = related_building.read_text(encoding="utf-8", errors="replace")
            block = f"""

## PDF_EXPORT picture evidence

- [[{s_slug}]] records picture metadata for `{place}`.
- Materials context: `{material}`
- Picture classification: `{classification}`
- Status: needs verification; picture metadata supports association but is not authoritative identity evidence.
"""
            if s_slug not in text:
                related_building.write_text(text.rstrip() + block + "\n", encoding="utf-8")
                print("linked", related_building)
                linked += 1

    print("pdf_export_total:", len(files))
    print("processed_new:", processed)
    print("skipped_existing:", skipped)
    print("building_links_added:", linked)

if __name__ == "__main__":
    main()
