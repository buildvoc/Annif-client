#!/usr/bin/env python3
from pathlib import Path
import re, json

WIKI = Path("wiki")
OUT = Path("output")

TYPE_BY_DIR = {
    "buildings": "building",
    "sources": "source",
    "places": "place",
    "streets": "street",
    "themes": "theme",
    "collections": "collection",
}

LABEL_BY_TYPE = {
    "source": "evidenced by",
    "place": "associated place",
    "street": "associated street",
    "theme": "associated theme",
    "collection": "in collection",
    "building": "related building",
}

def page_type(path):
    return TYPE_BY_DIR.get(path.parent.name, path.parent.name)

def label_for(to_type):
    return LABEL_BY_TYPE.get(to_type, "related to")

def extract_links(text):
    links = []

    # Obsidian/wiki style: [[slug]]
    for slug in re.findall(r"\[\[([^\]]+)\]\]", text):
        links.append(slug.strip())

    # Markdown style: [label](../places/farnham.md)
    for target in re.findall(r"\[[^\]]+\]\(([^)]+\.md)\)", text):
        slug = Path(target).stem
        if slug:
            links.append(slug)

    return links

SKIP_SLUGS = {
    "theme-source-documents",
    "theme-building-entity",
    "theme-place-entity",
    "theme-architectural-feature",
    "theme-associative-trail",
}

pages = {p.stem: p for p in WIKI.rglob("*.md")}
edges = []
seen = set()

for from_slug, path in sorted(pages.items()):
    text = path.read_text(encoding="utf-8", errors="replace")
    from_type = page_type(path)

    for to_slug in extract_links(text):
        if to_slug not in pages or from_slug == to_slug or to_slug in SKIP_SLUGS or from_slug in SKIP_SLUGS:
            continue

        to_type = page_type(pages[to_slug])
        label = label_for(to_type)
        key = (from_slug, to_slug, label)

        if key in seen:
            continue

        seen.add(key)
        edges.append({
            "from": from_slug,
            "from_type": from_type,
            "to": to_slug,
            "to_type": to_type,
            "label": label,
        })

OUT.mkdir(exist_ok=True)
(OUT / "building_memex_edges.json").write_text(
    json.dumps({"edges": edges}, indent=2),
    encoding="utf-8",
)

print("edges:", len(edges))
print("wrote output/building_memex_edges.json")
