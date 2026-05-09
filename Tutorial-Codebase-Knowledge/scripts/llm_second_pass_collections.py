#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path
from datetime import date

import requests
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pocketflow import Flow
from nodes import IdentifyAbstractions, AnalyzeRelationships


class SafeIdentifyAbstractions(IdentifyAbstractions):
    def prep(self, shared):
        self._files_for_fallback = shared.get("files", [])
        return super().prep(shared)

    def exec_fallback(self, prep_res, exc):
        print(f"IdentifyAbstractions failed; using file-based fallback abstractions: {exc}")
        out = []
        for i, (path, content) in enumerate(self._files_for_fallback[:50]):
            name = Path(path).stem.replace("-", " ").replace("_", " ").title()
            out.append({
                "name": name,
                "description": f"Wiki page used as fallback abstraction for collection analysis: {path}",
                "files": [i],
            })
        return out


class SafeAnalyzeRelationships(AnalyzeRelationships):
    def exec_fallback(self, prep_res, exc):
        print(f"AnalyzeRelationships failed; continuing with empty relationships: {exc}")
        return {
            "summary": "Needs verification: relationship analysis failed.",
            "relationships": [],
        }


ROOT = Path(".")
WIKI = ROOT / "wiki"
OUTPUT = ROOT / "output"


def slug(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "page"


def read_pages(*dirs):
    pages = []
    for d in dirs:
        base = WIKI / d
        if not base.exists():
            continue
        for p in sorted(base.glob("*.md")):
            pages.append((str(p), p.read_text(encoding="utf-8", errors="replace")))
    return pages


def call_ollama_json(prompt):
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "gemma3:4b-it-q4_K_M")
    r = requests.post(
        base_url + "/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_ctx": 4096},
        },
        timeout=900,
    )
    r.raise_for_status()
    return r.json().get("response", "")


def replace_index_collections(collections):
    index = WIKI / "index.md"
    text = index.read_text(encoding="utf-8") if index.exists() else "# Building Memex Wiki Index\n\n"

    block = "## Collections\n" + (
        "\n".join(f"- [[{c['slug']}]] — {c['title']}" for c in collections)
        if collections else "- None identified."
    ) + "\n"

    if "## Collections" in text:
        text = re.sub(r"## Collections\n[\s\S]*?(?=\n## |\Z)", block, text)
    else:
        text = text.rstrip() + "\n\n" + block

    index.write_text(text, encoding="utf-8")


def main():
    OUTPUT.mkdir(exist_ok=True)
    (WIKI / "collections").mkdir(parents=True, exist_ok=True)

    pages = read_pages("sources", "buildings", "places", "streets", "themes")
    if not pages:
        raise SystemExit("No wiki pages found for second pass")

    shared = {
        "files": pages,
        "project_name": "building-memex-collections",
        "language": "English",
        "use_cache": False,
        "max_abstraction_num": 50,
    }

    identify = SafeIdentifyAbstractions(max_retries=2, wait=5)
    analyze = SafeAnalyzeRelationships(max_retries=2, wait=5)
    identify >> analyze
    Flow(start=identify).run(shared)

    abstractions = shared.get("abstractions", [])
    relationships = shared.get("relationships", {})

    (OUTPUT / "collections_second_pass_abstractions.json").write_text(
        json.dumps(abstractions, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUTPUT / "collections_second_pass_relationships.json").write_text(
        json.dumps(relationships, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    building_pages = sorted((WIKI / "buildings").glob("*.md"))
    building_slugs = [p.stem for p in building_pages]

    source_context = "\n\n".join(
        f"## {path}\n{content[:4000]}" for path, content in pages
    )

    prompt = f"""
Return JSON only.

Task: create collection pages for a Building Memex wiki.

You must return an object with a "collections" array.
If there are existing building pages, create at least one collection.

Use ONLY the supplied wiki/source text.
Do not invent buildings.
Members must be selected only from this existing building slug list:
{json.dumps(building_slugs, ensure_ascii=False)}

Use AnalyzeRelationships output to help group related buildings/sources/themes:
{json.dumps(relationships, indent=2, ensure_ascii=False)}

Return this exact JSON shape:
{{
  "collections": [
    {{
      "slug": "lowercase-hyphen-collection-name",
      "title": "Readable collection title",
      "summary": "source-backed reason this collection exists",
      "members": ["existing-building-slug"],
      "source_pages": ["wiki/sources/source-name.md"],
      "inclusion_rules": ["rule"],
      "associative_trails": ["trail sentence"]
    }}
  ]
}}

Rules:
- Create collections only when evidence supports membership.
- Do not create empty collections.
- If unsure, use no collection.
- Do not use prose outside JSON.

Wiki/source text:
{source_context}
"""

    response = call_ollama_json(prompt)
    (OUTPUT / "collections_second_pass_response.txt").write_text(response, encoding="utf-8")

    data = json.loads(response)
    collections = data.get("collections", [])

    if not collections and building_slugs:
        collections = [
            {
                "slug": "existing-building-source-set",
                "title": "Existing Building Source Set",
                "summary": "Fallback collection grouping existing building pages for review.",
                "members": building_slugs,
                "source_pages": [],
                "inclusion_rules": ["Existing building page present in wiki/buildings."],
                "associative_trails": ["Second-pass fallback collection created because LLM returned no collections."]
            }
        ]

    valid = []

    for c in collections:
        members = [m for m in c.get("members", []) if m in building_slugs]
        if not members:
            continue

        c_slug = slug(c.get("slug") or c.get("title"))
        title = c.get("title") or c_slug.replace("-", " ").title()
        source_pages = c.get("source_pages", [])
        rules = c.get("inclusion_rules", [])
        trails = c.get("associative_trails", [])

        content = f"""# Collection: {title}

**Summary**: {c.get("summary", "Needs verification.")}

**Last updated**: {date.today().isoformat()}

---

## Members

""" + "\n".join(f"- [[{m}]]" for m in members) + """

## Sources

""" + ("\n".join(f"- {s}" for s in source_pages) if source_pages else "- Needs verification: source pages not supplied.") + """

## Inclusion rules

""" + ("\n".join(f"- {r}" for r in rules) if rules else "- Needs verification: inclusion rules not supplied.") + """

## Associative trails

""" + ("\n".join(f"- {t}" for t in trails) if trails else "- Needs verification: no trails supplied.") + "\n"

        out = WIKI / "collections" / f"{c_slug}.md"
        out.write_text(content, encoding="utf-8")
        print("wrote", out)
        valid.append({"slug": c_slug, "title": title})

    if valid:
        replace_index_collections(valid)
    else:
        print("No new collections returned; preserving existing index Collections section")

    log = WIKI / "log.md"
    if not log.exists():
        log.write_text("# Building Memex Wiki Log\n", encoding="utf-8")
    with log.open("a", encoding="utf-8") as f:
        f.write(f"\n## {date.today().isoformat()} — Second pass collections\n\n")
        f.write(f"**Collections written**: {len(valid)}\n")
        for c in valid:
            f.write(f"- [[{c['slug']}]]\n")

    print("collections written:", len(valid))


if __name__ == "__main__":
    main()
