#!/usr/bin/env python3
from pathlib import Path
import re
from collections import defaultdict

WIKI = Path("wiki")
COLLECTIONS = WIKI / "collections"
BUILDINGS = WIKI / "buildings"
INDEX = WIKI / "index.md"

BAD_SLUGS = {"empty", "none", "unknown", "null", "page", "n-a", "not-applicable"}

def title_of(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^#\s+(?:Collection:\s*)?(.+)$", text, re.M)
    return m.group(1).strip() if m else path.stem.replace("-", " ").title()

def links(text):
    return re.findall(r"\[\[([^\]]+)\]\]", text)

def section(text, heading):
    m = re.search(rf"## {re.escape(heading)}\n([\s\S]*?)(?=\n## |\Z)", text)
    return m.group(1) if m else ""

def unique_lines(lines):
    seen, out = set(), []
    for line in lines:
        line = line.rstrip()
        key = line.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out

def rewrite_links_everywhere(old, new):
    for p in WIKI.rglob("*.md"):
        s = p.read_text(encoding="utf-8", errors="replace")
        s2 = s.replace(f"[[{old}]]", f"[[{new}]]")
        if s2 != s:
            p.write_text(s2, encoding="utf-8")

def clean_collection_file(path, valid_buildings):
    s = path.read_text(encoding="utf-8", errors="replace")

    # Remove placeholder links.
    for bad in BAD_SLUGS:
        s = s.replace(f"[[{bad}]]", "Needs verification")

    # Clean Members section: only existing building slugs, deduped.
    member_slugs = []
    for link in links(section(s, "Members")):
        if link in valid_buildings and link not in member_slugs:
            member_slugs.append(link)

    if not member_slugs:
        path.unlink()
        print("deleted empty/invalid collection:", path)
        return None

    members_block = "## Members\n\n" + "\n".join(f"- [[{m}]]" for m in member_slugs) + "\n"
    if "## Members" in s:
        s = re.sub(r"## Members\n[\s\S]*?(?=\n## |\Z)", members_block, s)
    else:
        s = s.rstrip() + "\n\n" + members_block

    # Deduplicate bullet lines inside common sections.
    for heading in ["Sources", "Inclusion rules", "Associative trails", "Uncertain candidates", "Related pages"]:
        if f"## {heading}" not in s:
            continue
        body = section(s, heading)
        lines = unique_lines(body.splitlines())
        new_block = f"## {heading}\n" + "\n".join(lines).rstrip() + "\n"
        s = re.sub(rf"## {re.escape(heading)}\n[\s\S]*?(?=\n## |\Z)", new_block, s)

    path.write_text(s, encoding="utf-8")
    return tuple(sorted(member_slugs))

def rebuild_index_collections():
    collections = sorted(COLLECTIONS.glob("*.md"))
    block = "## Collections\n"
    if collections:
        block += "\n".join(f"- [[{p.stem}]] — {title_of(p)}" for p in collections) + "\n"
    else:
        block += "- None identified.\n"

    text = INDEX.read_text(encoding="utf-8", errors="replace") if INDEX.exists() else "# Building Memex Wiki Index\n\n"
    if "## Collections" in text:
        text = re.sub(r"## Collections\n[\s\S]*?(?=\n## |\Z)", block, text)
    else:
        text = text.rstrip() + "\n\n" + block

    INDEX.write_text(text, encoding="utf-8")

def main():
    COLLECTIONS.mkdir(parents=True, exist_ok=True)

    # Remove placeholder collection files.
    for bad in BAD_SLUGS:
        p = COLLECTIONS / f"{bad}.md"
        if p.exists():
            p.unlink()
            print("deleted placeholder:", p)

    valid_buildings = {p.stem for p in BUILDINGS.glob("*.md")}
    signatures = defaultdict(list)

    for p in sorted(COLLECTIONS.glob("*.md")):
        sig = clean_collection_file(p, valid_buildings)
        if sig:
            title_key = re.sub(r"[^a-z0-9]+", "-", title_of(p).lower()).strip("-")
            signatures[(title_key, sig)].append(p)

    # Merge exact duplicate collections: same normalized title + same members.
    for (_title_key, _sig), files in signatures.items():
        if len(files) <= 1:
            continue
        keep = sorted(files, key=lambda x: (len(x.stem), x.stem))[0]
        for dup in files:
            if dup == keep:
                continue
            rewrite_links_everywhere(dup.stem, keep.stem)
            dup.unlink()
            print("merged duplicate:", dup, "->", keep)

    rebuild_index_collections()

    print("collections:", len(list(COLLECTIONS.glob('*.md'))))
    print("done")

if __name__ == "__main__":
    main()
