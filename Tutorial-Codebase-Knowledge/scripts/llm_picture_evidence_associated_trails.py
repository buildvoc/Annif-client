#!/usr/bin/env python3
import argparse, json, os, re
from pathlib import Path
from datetime import datetime
import requests


def slug(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "page"


def source_slug_from_raw_name(name):
    base = Path(name).name
    base = re.sub(r"\.json$", "", base)
    base = base.replace(".annotated.arch_materials.description_classification", "")
    base = base.replace(".annotated.arch_materials", "")
    return "source-" + slug(base.replace("_", " "))


def extract_section(text, heading):
    m = re.search(rf"\n## {re.escape(heading)}\n(.*?)(?=\n## |\Z)", "\n" + text, flags=re.S)
    return m.group(1).strip() if m else ""


def replace_section(text, heading, body):
    pattern = rf"\n## {re.escape(heading)}\n.*?(?=\n## |\Z)"
    section = f"\n## {heading}\n\n{body.rstrip()}\n"
    if re.search(pattern, "\n" + text, flags=re.S):
        return re.sub(pattern, section, "\n" + text, flags=re.S).lstrip()
    return text.rstrip() + "\n" + section


def page_title(path):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# "):
            return line.lstrip("# ").strip()
    return path.stem


def raw_name_from_source_page(text):
    m = re.search(r"\*\*Raw file\*\*:\s*raw/docling-json/([^\n`]+)", text)
    return m.group(1).strip() if m else ""


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def walk_picture_evidence(obj, out, path="$"):
    if isinstance(obj, dict):
        keys = {str(k).lower() for k in obj}
        if (
            "pictures" in keys or "picture_classification" in keys or
            "picture_class" in keys or "materials_context" in keys or
            "caption" in keys or "meta" in keys
        ):
            out.append({k: v for k, v in obj.items() if str(k).lower() in {
                "self_ref", "page_no", "caption", "text", "picture_class",
                "picture_classification", "materials_context", "meta",
                "description", "provenance", "annotations"
            }})
        for v in obj.values():
            walk_picture_evidence(v, out, path)
    elif isinstance(obj, list):
        for v in obj:
            walk_picture_evidence(v, out, path)


def collect_texts(data, limit=40):
    texts = []
    for t in data.get("texts", []) if isinstance(data.get("texts"), list) else []:
        if isinstance(t, dict):
            val = t.get("text", "")
        else:
            val = str(t)
        val = re.sub(r"\s+", " ", val).strip()
        if val:
            texts.append(val)
    return texts[:limit]


def compact_json(obj, limit=9000):
    s = json.dumps(obj, indent=2, ensure_ascii=False)
    return s[:limit]


def extract_markdown_related_candidates(text, wiki, src_page, targets):
    found = []
    for m in re.findall(r"\]\(([^)]+\.md)\)", text):
        q = (src_page.parent / m).resolve()
        try:
            rel = q.relative_to(wiki.resolve())
        except Exception:
            continue
        stem = Path(rel).stem
        if stem in targets:
            found.append(stem)
    return found


def build_candidate_targets(search_blob, full_text, wiki, src_page, targets):
    candidates = set()

    # Strong candidates: already linked source related pages.
    candidates.update(extract_markdown_related_candidates(full_text, wiki, src_page, targets))

    # Medium candidates: exact slug/title token match in source text or picture metadata.
    for slug_name, target in targets.items():
        title = target["title"].lower()
        slug_tokens = [x for x in slug_name.split("-") if len(x) >= 4]
        title_tokens = [x for x in re.split(r"[^a-z0-9]+", title) if len(x) >= 4]

        if slug_name in search_blob or title in search_blob:
            candidates.add(slug_name)
            continue

        # Require at least two useful token hits to avoid broad false positives like "church".
        hits = sum(1 for tok in set(slug_tokens + title_tokens) if tok in search_blob)
        if hits >= 2:
            candidates.add(slug_name)

    # Keep only useful entity targets for picture trails.
    candidates = [
        c for c in candidates
        if targets[c]["kind"] in {"building", "place", "street"}
    ]

    return [targets[c] for c in sorted(candidates)][:40]

def wiki_targets(root):
    targets = {}
    for folder in ("buildings", "places", "streets", "collections"):
        for p in (root / folder).glob("*.md"):
            targets[p.stem] = {
                "slug": p.stem,
                "kind": folder[:-1],
                "path": str(p.relative_to(root)),
                "title": page_title(p),
            }
    return targets


def call_ollama(prompt):
    base = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
    r = requests.post(
        base + "/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "8192")),
            },
        },
        timeout=int(os.getenv("PICTURE_TRAILS_TIMEOUT", "900")),
    )
    r.raise_for_status()
    return r.json().get("response", "")


def extract_json(text):
    dec = json.JSONDecoder()
    for i, ch in enumerate(text or ""):
        if ch == "{":
            try:
                obj, _ = dec.raw_decode(text[i:])
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki-dir", default="wiki")
    ap.add_argument("--raw-dir", default="raw/docling-json")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    wiki = Path(args.wiki_dir)
    raw_dir = Path(args.raw_dir)
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)

    targets = wiki_targets(wiki)
    source_pages = sorted((wiki / "sources").glob("*.md"))
    if args.limit:
        source_pages = source_pages[:args.limit]

    results = []

    for src_page in source_pages:
        text = src_page.read_text(encoding="utf-8", errors="replace")
        raw_name = raw_name_from_source_page(text)
        raw_path = raw_dir / raw_name if raw_name else None
        data = read_json(raw_path) if raw_path and raw_path.exists() else {}

        picture_items = []
        walk_picture_evidence(data, picture_items)
        backend_section = extract_section(text, "Backend-rag picture evidence")
        extracted_text = extract_section(text, "Extracted text snippets") or "\n".join(collect_texts(data))

        if not picture_items and not backend_section:
            continue

        search_blob = (src_page.stem + " " + raw_name + " " + extracted_text + " " + backend_section + " " + compact_json(picture_items, 3000)).lower()
        target_preview = build_candidate_targets(search_blob, text, wiki, src_page, targets)
        if not target_preview:
            continue

        prompt = f"""
Return JSON only.

Task: review ALL picture evidence for this source and create cautious associated trails.

Rules:
- Use ONLY supplied source text, Backend-rag picture evidence, and raw picture metadata.
- Picture evidence supports visual association only.
- Do not use picture evidence as authoritative identity, address, coordinates, listing, or dating evidence.
- Link only to candidate target slugs.
- You are validating candidate targets, not discovering new ones.
- Prefer existing related-page links plus explicit raw metadata/source text.
- Reject generic/logo/noise-only picture evidence.
- If candidates are not supported by picture/source evidence, return no links.
- Output:
{{
  "source_summary": "one cautious sentence",
  "links": [
    {{"target_slug": "allowed-slug", "relationship": "visual_association|place_association|building_element_association|uncertain_association", "rationale": "short source-backed reason"}}
  ],
  "uncertainties": ["short uncertainty"]
}}

Source page: {src_page.relative_to(wiki)}
Raw file: {raw_name}

Source text:
{extracted_text[:3000]}

Backend-rag picture evidence:
{backend_section[:5000]}

Raw picture evidence:
{compact_json(picture_items, 9000)}

Candidate target pages:
{json.dumps(target_preview, indent=2, ensure_ascii=False)}
"""

        try:
            plan = extract_json(call_ollama(prompt))
        except Exception as e:
            plan = {"source_summary": "", "links": [], "uncertainties": [f"LLM failed: {e}"]}

        valid_links = []
        reviews = plan.get("candidate_reviews", plan.get("links", []))
        for link in reviews:
            if not isinstance(link, dict):
                continue
            if not link.get("supported", True):
                continue
            if link.get("target_slug") in targets:
                target = targets[link["target_slug"]]
                valid_links.append({
                    "target_slug": target["slug"],
                    "target_path": target["path"],
                    "relationship": link.get("relationship", "uncertain_association"),
                    "rationale": link.get("rationale", "Needs verification."),
                })

        if not valid_links:
            # Deterministic fallback: LLM did not approve links, but candidate generation found
            # source-backed page/title matches. Keep these as cautious associations, not claims.
            for target in target_preview[:8]:
                tslug = target["slug"]
                ttitle = target["title"].lower()
                if tslug in search_blob or ttitle in search_blob:
                    valid_links.append({
                        "target_slug": target["slug"],
                        "target_path": target["path"],
                        "relationship": "uncertain_association",
                        "rationale": "Candidate target appears in source text, captions, picture metadata, or existing related links; picture evidence requires manual verification.",
                    })

        result = {
            "source_page": str(src_page.relative_to(wiki)),
            "raw_file": raw_name,
            "source_summary": plan.get("source_summary") or "Picture evidence reviewed; deterministic candidate trail fallback used where LLM returned no supported links.",
            "links": valid_links,
            "uncertainties": plan.get("uncertainties", []),
        }
        results.append(result)

        body = [
            f"**Summary**: {result['source_summary']}",
            "",
            "**Evidence rule**: picture evidence supports visual association only; it is not authoritative identity, address, coordinate, listing, or dating evidence.",
            "",
            "### Associated pages",
        ]
        if valid_links:
            for link in valid_links:
                rel = os.path.relpath(wiki / link["target_path"], src_page.parent)
                body.append(f"- [{link['target_slug']}]({rel}) — `{link['relationship']}` — {link['rationale']}")
        else:
            body.append("- Needs verification: no safe associated page selected from picture evidence.")

        if result["uncertainties"]:
            body += ["", "### Uncertainties"]
            body += [f"- {u}" for u in result["uncertainties"]]

        if not args.dry_run:
            src_page.write_text(replace_section(text, "Picture evidence associated trails", "\n".join(body)), encoding="utf-8")

    coll = wiki / "collections" / "picture-evidence-associated-trails.md"
    coll_body = [
        "# Collection: Picture Evidence Associated Trails",
        "",
        "**Summary**: LLM-reviewed associated trails from all available source-page and raw Docling picture evidence.",
        "",
        f"**Last updated**: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "---",
        "",
        "## Members",
        "",
    ]
    for r in results:
        coll_body.append(f"- [{Path(r['source_page']).stem}](../{r['source_page']}) — {r['source_summary']}")
        for link in r["links"]:
            coll_body.append(f"  - [{link['target_slug']}](../{link['target_path']}) — `{link['relationship']}`")

    if not args.dry_run:
        coll.parent.mkdir(parents=True, exist_ok=True)
        coll.write_text("\n".join(coll_body) + "\n", encoding="utf-8")
        (out_dir / "picture_evidence_associated_trails.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print("picture_review_sources:", len(results))
    print("linked_sources:", sum(1 for r in results if r["links"]))
    print("links:", sum(len(r["links"]) for r in results))
    print("wrote:", coll)


if __name__ == "__main__":
    main()
