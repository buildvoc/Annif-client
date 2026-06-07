#!/usr/bin/env python3
import re
from pathlib import Path
from datetime import date

ROOT = Path(".")
WIKI = ROOT / "wiki"
OUTPUT = ROOT / "output"

def read(path):
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

def title(path):
    for line in read(path).splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ").title()

def wikilinks(text):
    return re.findall(r"\[\[([^\]]+)\]\]", text)

def page_slugs(folder):
    base = WIKI / folder
    return {p.stem: p for p in base.glob("*.md")} if base.exists() else {}

def replace_index_collections(collections):
    index = WIKI / "index.md"
    text = read(index) or "# Building Memex Wiki Index\n\n"
    block = "## Collections\n" + "\n".join(f"- [[{c}]]" for c in sorted(collections)) + "\n"
    if "## Collections" in text:
        text = re.sub(r"## Collections\n[\s\S]*?(?=\n## |\Z)", block, text)
    else:
        text = text.rstrip() + "\n\n" + block
    index.write_text(text, encoding="utf-8")

def write_collection(slug, heading, reason, members, trail_lines):
    members = sorted(set(members))
    if len(members) < 2:
        return None

    out = WIKI / "collections" / f"{slug}.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    out.write_text(f"""# Collection: {heading}

**Reason**: {reason}

**Last updated**: {date.today().isoformat()}

---

## Members

""" + "\n".join(f"- [[{m}]]" for m in members) + """

## Associative trails

""" + "\n".join(f"- {t}" for t in trail_lines) + "\n", encoding="utf-8")

    print("wrote", out)
    return slug

def ensure_missing_theme_pages():
    """Create placeholder theme pages for unresolved wiki links that look like theme slugs."""
    existing = {p.stem for p in WIKI.rglob("*.md")}
    missing = set()

    for page in WIKI.rglob("*.md"):
        text = read(page)
        for link in wikilinks(text):
            if link in existing:
                continue
            # Only auto-create concept/theme-like links, not buildings/places/sources.
            if (
                link.startswith("theme-")
                or link in {"arts-and-crafts", "architectural-heritage"}
                or "architecture" in link
                or "heritage" in link
                or "craft" in link
            ):
                missing.add(link)

    theme_dir = WIKI / "themes"
    theme_dir.mkdir(parents=True, exist_ok=True)

    for slug in sorted(missing):
        title = slug
        if title.startswith("theme-"):
            title = title[6:]
        title = title.replace("-", " ").title()

        out = theme_dir / f"{slug}.md"
        if not out.exists():
            out.write_text(f"""# Theme: {title}

**Summary**: Auto-created theme page for unresolved associative trail link.

**Status**: needs verification

## Related pages

""", encoding="utf-8")
            print("created missing theme", out)


def main():
    OUTPUT.mkdir(exist_ok=True)
    (WIKI / "collections").mkdir(parents=True, exist_ok=True)

    buildings = page_slugs("buildings")
    places = page_slugs("places")
    streets = page_slugs("streets")
    themes = page_slugs("themes")
    sources = page_slugs("sources")

    if not buildings:
        raise SystemExit("No building pages found for second pass")

    written = []

    # building -> linked place/street/theme/source trails
    groups = {
        "place": {},
        "street": {},
        "theme": {},
        "source": {},
    }

    for b_slug, b_path in buildings.items():
        text = read(b_path)
        links = set(wikilinks(text))

        for p in links & set(places):
            groups["place"].setdefault(p, []).append(b_slug)

        for s in links & set(streets):
            groups["street"].setdefault(s, []).append(b_slug)

        for t in links & set(themes):
            groups["theme"].setdefault(t, []).append(b_slug)

        for src in links & set(sources):
            groups["source"].setdefault(src, []).append(b_slug)

        # Also infer source trails from raw/docling-json source paths inside building page
        for raw_name in re.findall(r"raw/docling-json/([^ )\n]+)", text):
            raw_slug = "source-" + re.sub(r"[^a-z0-9]+", "-", raw_name.lower())
            raw_slug = raw_slug.replace("-annotated-arch-materials-description-classification-json", "").strip("-")
            if raw_slug in sources:
                groups["source"].setdefault(raw_slug, []).append(b_slug)

    for p_slug, members in sorted(groups["place"].items()):
        c = write_collection(
            f"place-{p_slug}-buildings",
            f"Buildings associated with {title(places[p_slug])}",
            "Buildings linked to the same place page.",
            members,
            [f"[[{m}]] → [[{p_slug}]] — associated place" for m in sorted(set(members))]
        )
        if c: written.append(c)

    for s_slug, members in sorted(groups["street"].items()):
        c = write_collection(
            f"street-{s_slug}-buildings",
            f"Buildings associated with {title(streets[s_slug])}",
            "Buildings linked to the same street page.",
            members,
            [f"[[{m}]] → [[{s_slug}]] — associated street" for m in sorted(set(members))]
        )
        if c: written.append(c)

    for t_slug, members in sorted(groups["theme"].items()):
        c = write_collection(
            f"theme-{t_slug}-buildings",
            f"Buildings associated with {title(themes[t_slug])}",
            "Buildings linked to the same theme page.",
            members,
            [f"[[{m}]] → [[{t_slug}]] — shared theme" for m in sorted(set(members))]
        )
        if c: written.append(c)

    for src_slug, members in sorted(groups["source"].items()):
        c = write_collection(
            f"source-{src_slug}-buildings",
            f"Buildings evidenced by {title(sources[src_slug])}",
            "Buildings connected to the same source page.",
            members,
            [f"[[{src_slug}]] → [[{m}]] — evidence source" for m in sorted(set(members))]
        )
        if c: written.append(c)

    replace_index_collections(written)

    log = WIKI / "log.md"
    if not log.exists():
        log.write_text("# Building Memex Wiki Log\n", encoding="utf-8")
    with log.open("a", encoding="utf-8") as f:
        f.write(f"\n## {date.today().isoformat()} — Deterministic second-pass trails and collections\n\n")
        f.write(f"**Collections written**: {len(written)}\n")
        for c in written:
            f.write(f"- [[{c}]]\n")

    print("collections written:", len(written))

if __name__ == "__main__":
    main()
