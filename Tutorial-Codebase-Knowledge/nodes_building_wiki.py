import json
import urllib.request
import urllib.error
import os
import re
import requests
from pathlib import Path
from datetime import date, datetime

from pocketflow import Node
from utils.call_llm import call_llm
from nodes import IdentifyAbstractions, AnalyzeRelationships


def slug(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "page"


def clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def is_placeholder_entity(text):
    return slug(text) in {"", "page", "empty", "none", "unknown", "null", "n-a", "not-applicable"}


def extract_json_dict(text, required_key=None):
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text or ""):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
        except Exception:
            continue
        if isinstance(obj, dict) and (required_key is None or required_key in obj):
            return obj
    return None


def normalise_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if v not in (None, "")]
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []



def backend_rag_post_json(path, payload, timeout=120):
    api_base = os.environ.get("BACKEND_RAG_API_BASE", "http://192.168.1.142:8001").rstrip("/")
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{api_base}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def picture_evidence_section_for_doc(doc):
    source_file = Path(str(doc.get("name", ""))).name
    if not source_file.endswith(".json"):
        return ""

    section = [
        "---",
        "",
        "## Backend-rag picture evidence",
        "",
        f"- API source_file: `{source_file}`",
    ]

    try:
        inv = backend_rag_post_json(
            "/api/pictures",
            {"source_file": source_file, "query": "", "limit": 50},
            timeout=60,
        )
        pics = inv.get("results", [])
        section.append(f"- Picture inventory count: `{len(pics)}`")
        for pic in pics[:12]:
            section.append(
                f"- page `{pic.get('page_no')}` | `{pic.get('picture_ref')}` | "
                f"class `{pic.get('picture_class')}` | "
                f"caption `{pic.get('caption') or ''}` | "
                f"docling `{str(pic.get('docling_description') or '')[:240]}`"
            )
    except Exception as e:
        section.append(f"- Picture inventory error: `{e}`")

    try:
        desc = backend_rag_post_json(
            "/api/describe-pictures",
            {
                "source_file": source_file,
                "query": "",
                "limit": 5,
                "model": os.environ.get("BACKEND_RAG_VISION_MODEL", "gemma4:12b"),
            },
            timeout=300,
        )
        descs = desc.get("results", [])
        section.append(f"- Gemma4 description count: `{len(descs)}`")
        for d in descs:
            section.append(
                f"- visual page `{d.get('page_no')}` | `{d.get('picture_ref')}` | "
                f"class `{d.get('picture_class')}` | "
                f"{str(d.get('gemma4_description') or '')[:500]}"
            )
    except Exception as e:
        section.append(f"- Gemma4 description error: `{e}`")

    section += [
        "",
        "Evidence rule: picture metadata and Gemma4 descriptions support visual association only; they are not authoritative identity, address, coordinate, listing, or dating evidence.",
        "",
    ]
    return "\n".join(section)

def rel_raw(doc):
    return f"raw/docling-json/{doc['name']}"


def call_ollama_json(prompt):
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "gemma4:12b")

    response = requests.post(
        base_url + "/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "num_ctx": 4096,
            },
        },
        timeout=900,
    )
    response.raise_for_status()
    text = response.json().get("response", "")
    Path("output").mkdir(exist_ok=True)
    Path("output/last_ollama_json_response.txt").write_text(text, encoding="utf-8")
    if not extract_json_dict(text):
        print("WARNING: Ollama returned no parseable JSON; see output/last_ollama_json_response.txt")
    return text


def source_title_from_name(name):
    return (
        Path(name).name
        .replace(".annotated.arch_materials.description_classification.json", "")
        .replace("_", " ")
        .strip()
    )


def source_slug_from_name(name):
    return "source-" + slug(source_title_from_name(name))


def source_names_to_docs(source_names, docs_by_name):
    docs = []
    seen = set()
    for name in normalise_list(source_names):
        key = Path(str(name)).name
        if key in docs_by_name and key not in seen:
            docs.append(docs_by_name[key])
            seen.add(key)
    return docs


def source_refs_from_names(source_names):
    refs = []
    for name in normalise_list(source_names):
        refs.append(f"raw/docling-json/{Path(str(name)).name}")
    return refs


def make_source_blocks(docs, limit=60):
    blocks = []
    for doc in docs:
        text = "\n".join(f"- {t}" for t in doc["texts"][:limit])
        blocks.append(f"## {doc['name']}\n{text}")
    return "\n\n".join(blocks)



def _source_marker_slug(path):
    name = Path(str(path)).name
    name = name.replace(".annotated.arch_materials.description_classification.json", "")
    name = name.replace(".json", "")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return "source-" + slug


def _write_processed_source_marker(path, texts):
    """Write durable source marker before LLM entity extraction."""
    out_dir = Path("wiki/sources")
    out_dir.mkdir(parents=True, exist_ok=True)

    slug = _source_marker_slug(path)
    out = out_dir / f"{slug}.md"

    raw_path = str(path)
    if raw_path.startswith("/app/"):
        raw_path = raw_path.replace("/app/", "", 1)

    preview = []
    for t in texts[:12]:
        txt = t.get("text", "") if isinstance(t, dict) else str(t)
        txt = " ".join(txt.split())
        if txt:
            preview.append(txt[:500])

    title = slug.replace("source-", "").replace("-", " ").title()

    content = f"""# Source: {title}

**Raw file**: {raw_path}  
**Status**: processed  
**Processed at**: {datetime.now().strftime("%Y-%m-%d %H:%M")}

## Extracted text preview

""" + "\n\n".join(f"- {x}" for x in preview) + "\n"

    if not out.exists():
        out.write_text(content, encoding="utf-8")
        print(f"processed source marker: {out}")


class FetchDoclingDocuments(Node):
    def prep(self, shared):
        return Path(shared.get("raw_dir", "raw/docling-json")), shared.get("limit"), shared.get("offset", 0)

    def exec(self, prep_res):
        raw_dir, limit, offset = prep_res
        print(f"Crawling DoclingDocuments: {raw_dir}")
        files = sorted(raw_dir.glob("*.json"))
        offset = int(offset or 0)
        if limit:
            files = files[offset:offset + int(limit)]
        elif offset:
            files = files[offset:]
        if not files:
            raise ValueError(f"No DoclingDocument JSON files found in {raw_dir}")

        docs = []
        for i, path in enumerate(files, 1):
            data = json.loads(path.read_text(encoding="utf-8"))
            texts = []
            for item in data.get("texts", []):
                txt = clean(item.get("text") or item.get("orig") or "")
                if len(txt) > 20:
                    texts.append(txt)

            docs.append({"path": str(path), "name": path.name, "texts": texts[:160]})
            print(f"Progress: {i}/{len(files)} ({int(i / len(files) * 100)}%) {path.name} [processed]")

        return docs

    def post(self, shared, prep_res, exec_res):
        for doc in exec_res:
            _write_processed_source_marker(doc.get("path", ""), doc.get("texts", []))

        shared["docling_documents"] = exec_res
        shared["files"] = [(rel_raw(doc), "\n".join(doc["texts"])) for doc in exec_res]
        shared.setdefault("project_name", "building-memex")
        shared.setdefault("language", "English")
        shared.setdefault("max_abstraction_num", 100)



class SafeIdentifyAbstractions(IdentifyAbstractions):
    def exec_fallback(self, prep_res, exc):
        print(f"Abstraction identification failed; continuing with safe Building Memex abstractions: {exc}")

        file_count = 1
        try:
            file_count = prep_res[2]
        except Exception:
            pass

        files = list(range(file_count))

        return [
            {
                "name": "Source Documents",
                "description": "DoclingDocument JSON source files used as immutable evidence for the Building Memex wiki.",
                "files": files,
            },
            {
                "name": "Building Entity",
                "description": "Buildings or architectural sites identified from the source documents.",
                "files": files,
            },
            {
                "name": "Place Entity",
                "description": "Places, streets, towns, or locations mentioned in the source documents.",
                "files": files,
            },
            {
                "name": "Architectural Feature",
                "description": "Architectural elements, materials, fittings, monuments, or historic features described in the sources.",
                "files": files,
            },
            {
                "name": "Associative Trail",
                "description": "Relationships between sources, buildings, places, collections, and themes.",
                "files": files,
            },
        ]


class SafeAnalyzeRelationships(AnalyzeRelationships):
    def exec_fallback(self, prep_res, exc):
        print(f"Relationship analysis failed; continuing with empty relationships: {exc}")
        return {
            "summary": "Needs verification: relationship analysis failed or returned invalid indices.",
            "relationships": [],
        }


def normalise_entity_plan(plan, docs):
    docs_by_name = {doc["name"]: doc for doc in docs}
    normalised = {
        "buildings": [],
        "places": [],
        "streets": [],
        "collections": [],
    }

    if not normalise_list(plan.get("buildings")) and len(docs) == 1:
        doc = docs[0]
        fallback_title = source_title_from_name(doc["name"])
        if "st andrews church" in slug(fallback_title).replace("-", " ") or "st-andrews-church" in slug(fallback_title):
            plan["buildings"] = [{
                "slug": "st-andrews-church-farnham",
                "title": "St Andrew's Church, Farnham",
                "status": "needs verification",
                "summary": "Deterministic fallback from source title after LLM entity JSON parsing failed.",
                "source_names": [doc["name"]],
                "place_slug": "farnham",
                "street_slug": "",
                "collection_slugs": ["st-andrews-church-evidence"],
                "theme_slugs": ["building-entity", "source-documents"],
                "keywords": ["st andrews church", "farnham", "church"],
                "claims": [{"text": "Source file title identifies St Andrews Church, Farnham.", "source_name": doc["name"]}],
                "uncertainties": ["Fallback entity requires verification against source text and authoritative records."]
            }]

    for raw in normalise_list(plan.get("buildings")):
        if isinstance(raw, str):
            raw = {
                "title": raw,
                "source_names": [doc["name"] for doc in docs],
                "status": "needs verification",
                "summary": "Needs verification: extracted as a simple building/entity string.",
                "keywords": [raw],
            }
        if not isinstance(raw, dict):
            continue
        title = clean(raw.get("title") or raw.get("name"))
        source_names = [Path(str(x)).name for x in normalise_list(raw.get("source_names"))]
        source_names = [x for x in source_names if x in docs_by_name]
        if not title or is_placeholder_entity(title) or not source_names:
            continue

        b = {
            "slug": slug(raw.get("slug") or title),
            "title": title,
            "status": clean(raw.get("status") or "needs verification"),
            "summary": clean(raw.get("summary") or ""),
            "source_names": source_names,
            "place_slug": slug(raw.get("place_slug")) if raw.get("place_slug") else "",
            "street_slug": slug(raw.get("street_slug")) if raw.get("street_slug") else "",
            "collection_slugs": [slug(x) for x in normalise_list(raw.get("collection_slugs"))],
            "theme_slugs": [slug(x) for x in normalise_list(raw.get("theme_slugs"))],
            "keywords": [clean(x).lower() for x in normalise_list(raw.get("keywords"))],
            "claims": [x for x in normalise_list(raw.get("claims")) if isinstance(x, dict)],
            "uncertainties": [clean(x) for x in normalise_list(raw.get("uncertainties"))],
        }
        normalised["buildings"].append(b)

    for kind in ("places", "streets"):
        for raw in normalise_list(plan.get(kind)):
            if isinstance(raw, str):
                raw = {
                    "title": raw,
                    "source_names": [doc["name"] for doc in docs],
                    "summary": "Needs verification: extracted as a simple place/street string.",
                }
            if not isinstance(raw, dict):
                continue
            title = clean(raw.get("title") or raw.get("name"))
            source_names = [Path(str(x)).name for x in normalise_list(raw.get("source_names"))]
            source_names = [x for x in source_names if x in docs_by_name]
            if not title or is_placeholder_entity(title):
                continue
            normalised[kind].append({
                "slug": slug(raw.get("slug") or title),
                "title": title,
                "summary": clean(raw.get("summary") or ""),
                "source_names": source_names,
            })

    for raw in normalise_list(plan.get("collections")):
        if isinstance(raw, str):
            raw = {
                "title": raw,
                "source_names": [doc["name"] for doc in docs],
                "members": [],
                "summary": "Needs verification: extracted as a simple collection/theme string.",
            }
        if not isinstance(raw, dict):
            continue
        title = clean(raw.get("title") or raw.get("name"))
        members = [slug(x) for x in normalise_list(raw.get("members"))]
        source_names = [Path(str(x)).name for x in normalise_list(raw.get("source_names"))]
        source_names = [x for x in source_names if x in docs_by_name]
        if not title:
            continue
        normalised["collections"].append({
            "slug": slug(raw.get("slug") or title),
            "title": title,
            "summary": clean(raw.get("summary") or ""),
            "source_names": source_names,
            "members": members,
            "inclusion_rules": [clean(x) for x in normalise_list(raw.get("inclusion_rules"))],
            "uncertain_candidates": [slug(x) for x in normalise_list(raw.get("uncertain_candidates"))],
        })

    # Add placeholder place/street pages only when the LLM has explicitly linked a building to a slug.
    existing_places = {p["slug"] for p in normalised["places"]}
    existing_streets = {s["slug"] for s in normalised["streets"]}

    for b in normalised["buildings"]:
        if b["place_slug"] and b["place_slug"] not in existing_places:
            normalised["places"].append({
                "slug": b["place_slug"],
                "title": b["place_slug"].replace("-", " ").title(),
                "summary": "Needs verification: place page derived from LLM entity relationship.",
                "source_names": b["source_names"],
            })
            existing_places.add(b["place_slug"])

        if b["street_slug"] and b["street_slug"] not in existing_streets:
            normalised["streets"].append({
                "slug": b["street_slug"],
                "title": b["street_slug"].replace("-", " ").title(),
                "summary": "Needs verification: street page derived from LLM entity relationship.",
                "source_names": b["source_names"],
            })
            existing_streets.add(b["street_slug"])

    # Add minimal collections only when the LLM has explicitly assigned collection slugs to a building.
    existing_collections = {c["slug"] for c in normalised["collections"]}
    for b in normalised["buildings"]:
        for c_slug in b["collection_slugs"]:
            if c_slug and c_slug not in existing_collections:
                normalised["collections"].append({
                    "slug": c_slug,
                    "title": c_slug.replace("-", " ").title(),
                    "summary": "Needs verification: collection page derived from LLM entity relationship.",
                    "source_names": b["source_names"],
                    "members": [b["slug"]],
                    "inclusion_rules": [],
                    "uncertain_candidates": [],
                })
                existing_collections.add(c_slug)

    return normalised


def extract_entity_plan(docs, schema, abstractions, relationships, use_cache):
    prompt = f"""
Return a JSON object only.

Do not explain.
Do not summarize.
Do not write markdown.
Do not use code fences.
The first character of your response must be an opening curly brace and the last character must be a closing curly brace.

Task: extract an entity plan for a private Building Memex wiki.

Use ONLY the supplied source text.
Do not invent buildings, places, streets, collections, dates, names, or identities.
If the source does not support an entity, omit it.
Use exact source filenames from the Sources section in source_names.

JSON shape:
{{
  "buildings": [
    {{
      "slug": "lowercase-hyphen-page-name",
      "title": "Source-backed building or site name",
      "status": "confirmed|uncertain",
      "summary": "one source-backed sentence",
      "source_names": ["exact-source-filename.json"],
      "place_slug": "place-page-slug-or-empty",
      "street_slug": "street-page-slug-or-empty",
      "collection_slugs": ["collection-page-slug"],
      "theme_slugs": ["theme-page-slug"],
      "keywords": ["terms for evidence matching"],
      "claims": [
        {{"text": "source-backed claim", "source_name": "exact-source-filename.json"}}
      ],
      "uncertainties": ["visible uncertainty if any"]
    }}
  ],
  "places": [
    {{
      "slug": "place-page-slug",
      "title": "Source-backed place name",
      "summary": "one source-backed sentence",
      "source_names": ["exact-source-filename.json"]
    }}
  ],
  "streets": [
    {{
      "slug": "street-page-slug",
      "title": "Source-backed street name",
      "summary": "one source-backed sentence",
      "source_names": ["exact-source-filename.json"]
    }}
  ],
  "collections": [
    {{
      "slug": "collection-page-slug",
      "title": "Source-backed collection name",
      "summary": "why these pages belong together",
      "source_names": ["exact-source-filename.json"],
      "members": ["building-page-slug"],
      "inclusion_rules": ["source-backed or clearly procedural rule"],
      "uncertain_candidates": ["building-page-slug"]
    }}
  ]
}}

Rules:
{schema}

Existing abstraction extraction:
{json.dumps(abstractions or [], indent=2, ensure_ascii=False)}

Existing relationship analysis:
{json.dumps(relationships or {}, indent=2, ensure_ascii=False)}

Sources:
{make_source_blocks(docs, limit=45)}
"""

    print("Extracting entity plan using LLM per source...")
    Path("output").mkdir(exist_ok=True)

    merged = {"buildings": [], "places": [], "streets": [], "collections": []}
    responses = []

    all_sources = make_source_blocks(docs, limit=45)

    for doc in docs:
        one_source = make_source_blocks([doc], limit=80)
        single_prompt = prompt.replace(all_sources, one_source)

        try:
            response = call_ollama_json(single_prompt)
        except Exception as e:
            print(f"Entity plan failed for {doc.get('name', 'unknown')}; skipping source: {e}")
            continue
        responses.append("## " + doc["name"] + "\n" + response + "\n")

        plan = extract_json_dict(response, required_key="buildings")
        if not isinstance(plan, dict):
            print("WARNING: no valid JSON entity plan for " + doc["name"])
            continue

        for key in ("buildings", "places", "streets", "collections"):
            val = plan.get(key, [])
            if isinstance(val, list):
                merged[key].extend(val)

    Path("output/building_wiki_entity_plan_response.txt").write_text(
        "\n\n".join(responses),
        encoding="utf-8",
    )

    normalised = normalise_entity_plan(merged, docs)
    Path("output/building_wiki_entity_plan.json").write_text(
        json.dumps(normalised, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        "Entity plan:",
        f"{len(normalised['buildings'])} buildings,",
        f"{len(normalised['places'])} places,",
        f"{len(normalised['streets'])} streets,",
        f"{len(normalised['collections'])} collections",
    )
    return normalised


def relationship_trails(abstractions, relationships):
    abstractions = abstractions or []
    relationships = relationships or {}
    rels = relationships.get("details") or relationships.get("relationships") or []

    trails = []
    for rel in rels:
        src = rel.get("from")
        dst = rel.get("to")
        if not isinstance(src, int) or not isinstance(dst, int):
            continue
        if src < 0 or dst < 0 or src >= len(abstractions) or dst >= len(abstractions):
            continue
        src_slug = f"theme-{slug(abstractions[src].get('name', 'theme'))}"
        dst_slug = f"theme-{slug(abstractions[dst].get('name', 'theme'))}"
        trails.append(f"- [[{src_slug}]] → [[{dst_slug}]] — {rel.get('label', 'related')}")
    return trails


def evidence_snippets(entity, group_docs):
    keywords = [clean(k).lower() for k in normalise_list(entity.get("keywords"))]
    snippets = []

    for claim in normalise_list(entity.get("claims")):
        if isinstance(claim, dict) and clean(claim.get("text")):
            snippets.append((Path(str(claim.get("source_name", ""))).name, clean(claim.get("text"))))

    for doc in group_docs:
        for txt in doc["texts"][:100]:
            lower = txt.lower()
            if not keywords or any(k and k in lower for k in keywords):
                snippets.append((doc["name"], txt))
            if len(snippets) >= 14:
                return snippets

    return snippets[:14]


def build_wiki_payload(docs, entity_plan, abstractions, relationships):
    today = date.today().isoformat()
    docs_by_name = {doc["name"]: doc for doc in docs}

    files = []
    theme_links = [f"theme-{slug(a.get('name', 'theme'))}" for a in (abstractions or [])]
    trails = relationship_trails(abstractions, relationships)

    buildings = entity_plan.get("buildings", [])
    places = entity_plan.get("places", [])
    streets = entity_plan.get("streets", [])
    collections = entity_plan.get("collections", [])

    # Source pages
    for doc in docs:
        source_slug = source_slug_from_name(doc["name"])
        source_title = source_title_from_name(doc["name"])

        related = []
        for b in buildings:
            if doc["name"] in b.get("source_names", []):
                related.append(f"- [[{b['slug']}]]")
        for p in places:
            if doc["name"] in p.get("source_names", []):
                related.append(f"- [[{p['slug']}]]")
        for st in streets:
            if doc["name"] in st.get("source_names", []):
                related.append(f"- [[{st['slug']}]]")
        for c in collections:
            if doc["name"] in c.get("source_names", []):
                related.append(f"- [[{c['slug']}]]")

        files.append({
            "path": f"wiki/sources/{source_slug}.md",
            "content": f"""# Source: {source_title}

**Summary**: Source page generated from DoclingDocument JSON.

**Raw file**: {rel_raw(doc)}

**Last ingested**: {today}

---

## Extracted text snippets

""" + "\n".join(f"- {t}" for t in doc["texts"][:30]) + """

""" + picture_evidence_section_for_doc(doc) + """

## Related pages

""" + ("\n".join(sorted(set(related))) if related else "- Needs verification: no related entity matched.")
        })

    # Building pages
    for b in buildings:
        group_docs = source_names_to_docs(b.get("source_names"), docs_by_name)
        snippets = evidence_snippets(b, group_docs)

        relationship_lines = []
        if b.get("place_slug"):
            relationship_lines.append(f"- In place: [[{b['place_slug']}]]")
        if b.get("street_slug"):
            relationship_lines.append(f"- On street: [[{b['street_slug']}]]")
        for c_slug in b.get("collection_slugs", []):
            relationship_lines.append(f"- In collection: [[{c_slug}]]")
        for t_slug in b.get("theme_slugs", []):
            relationship_lines.append(f"- Related theme: [[{t_slug}]]")

        uncertainty_lines = normalise_list(b.get("uncertainties"))
        if not uncertainty_lines:
            uncertainty_lines = ["Needs verification: authoritative identity, address, coordinates, and listing details."]

        files.append({
            "path": f"wiki/buildings/{b['slug']}.md",
            "content": f"""# {b['title']}

**Summary**: {b.get('summary') or 'Needs verification: summary not supplied by entity plan.'}

**Status**: {b.get('status') or 'needs verification'}

**Sources**:
""" + "\n".join(f"- {rel_raw(doc)}" for doc in group_docs) + f"""

**Last updated**: {today}

---

## Evidence snippets

""" + ("\n".join(
                f"- Claim/snippet: {txt}\n  - Source: raw/docling-json/{src}"
                for src, txt in snippets
            ) if snippets else "- Needs verification: no evidence snippets selected.") + """

## Relationships

""" + ("\n".join(relationship_lines) if relationship_lines else "- Needs verification: no relationships supplied by entity plan.") + """

## Associative trails

""" + ("\n".join(trails) if trails else "- Needs verification: no relationship trails generated.") + """

## Theme pages

""" + ("\n".join(f"- [[{x}]]" for x in theme_links) if theme_links else "- Needs verification: no theme pages generated.") + """

## Uncertainty

""" + "\n".join(f"- {u}" for u in uncertainty_lines) + """

## Related pages

""" + ("\n".join(line.replace(": ", ": ") for line in relationship_lines) if relationship_lines else "- Needs verification: no related pages.")
        })

    # Place pages
    for p in places:
        related_buildings = [b for b in buildings if b.get("place_slug") == p["slug"]]
        files.append({
            "path": f"wiki/places/{p['slug']}.md",
            "content": f"""# {p['title']}

**Summary**: {p.get('summary') or 'Needs verification: summary not supplied by entity plan.'}

**Sources**:
""" + "\n".join(source_refs_from_names(p.get("source_names"))) + f"""

**Last updated**: {today}

---

## Related buildings

""" + ("\n".join(f"- [[{b['slug']}]]" for b in related_buildings) if related_buildings else "- Needs verification: no related buildings.")
        })

    # Street pages
    for st in streets:
        related_buildings = [b for b in buildings if b.get("street_slug") == st["slug"]]
        files.append({
            "path": f"wiki/streets/{st['slug']}.md",
            "content": f"""# {st['title']}

**Summary**: {st.get('summary') or 'Needs verification: summary not supplied by entity plan.'}

**Sources**:
""" + "\n".join(source_refs_from_names(st.get("source_names"))) + f"""

**Last updated**: {today}

---

## Related buildings

""" + ("\n".join(f"- [[{b['slug']}]]" for b in related_buildings) if related_buildings else "- Needs verification: no related buildings.")
        })

    # Collection pages
    for c in collections:
        files.append({
            "path": f"wiki/collections/{c['slug']}.md",
            "content": f"""# Collection: {c['title']}

**Summary**: {c.get('summary') or 'Needs verification: summary not supplied by entity plan.'}

**Sources**:
""" + "\n".join(source_refs_from_names(c.get("source_names"))) + f"""

**Last updated**: {today}

---

## Inclusion rules

""" + ("\n".join(f"- {x}" for x in c.get("inclusion_rules", [])) if c.get("inclusion_rules") else "- Needs verification: inclusion rules not supplied.") + """

## Members

""" + ("\n".join(f"- [[{m}]]" for m in c.get("members", [])) if c.get("members") else "- Needs verification: no members supplied.") + """

## Associative trails

""" + ("\n".join(trails) if trails else "- Needs verification: no relationship trails generated.") + """

## Uncertain candidates

""" + ("\n".join(f"- [[{m}]]" for m in c.get("uncertain_candidates", [])) if c.get("uncertain_candidates") else "- None recorded.")
        })

    # Theme pages from existing Tutorial nodes
    for i, a in enumerate(abstractions or []):
        name = a.get("name", f"Theme {i}")
        t_slug = f"theme-{slug(name)}"

        outgoing = []
        for line in trails:
            if f"[[{t_slug}]] →" in line:
                outgoing.append(line)

        files.append({
            "path": f"wiki/themes/{t_slug}.md",
            "content": f"""# Theme: {name}

**Summary**: {clean(a.get('description')) or 'Needs verification: summary not supplied.'}

**Status**: needs verification

**Sources**:
- Derived from current DoclingDocument abstraction/relationship analysis.

## Related buildings

""" + ("\n".join(f"- [[{b['slug']}]]" for b in buildings) if buildings else "- Needs verification: no related buildings.") + """

## Related themes

""" + ("\n".join(outgoing) if outgoing else "- Needs verification: no outgoing theme relationships.")
        })

    # Index
    files.append({
        "path": "wiki/index.md",
        "content": "# Building Memex Wiki Index\n\n"
        + "## Sources\n"
        + "\n".join(f"- [[{source_slug_from_name(doc['name'])}]] — {source_title_from_name(doc['name'])}" for doc in docs)
        + "\n\n## Buildings\n"
        + ("\n".join(f"- [[{b['slug']}]] — {b['title']}" for b in buildings) if buildings else "- None identified.")
        + "\n\n## Places\n"
        + ("\n".join(f"- [[{p['slug']}]] — {p['title']}" for p in places) if places else "- None identified.")
        + "\n\n## Streets\n"
        + ("\n".join(f"- [[{s['slug']}]] — {s['title']}" for s in streets) if streets else "- None identified.")
        + "\n\n## Collections\n"
        + ("\n".join(f"- [[{c['slug']}]] — {c['title']}" for c in collections) if collections else "- None identified.")
        + "\n\n## Themes\n"
        + ("\n".join(f"- [[{x}]]" for x in theme_links) if theme_links else "- None identified.")
        + "\n"
    })

    files.append({
        "path": "wiki/log.md",
        "content": "# Building Memex Wiki Log\n"
    })

    return {
        "files": files,
        "log_append": f"""## {today} — LLM-assisted wiki ingest

**Status**: completed with LLM entity extraction.

**Sources ingested**:
""" + "\n".join(f"- {rel_raw(doc)}" for doc in docs) + """

**Counts**:
- Buildings: """ + str(len(buildings)) + """
- Places: """ + str(len(places)) + """
- Streets: """ + str(len(streets)) + """
- Collections: """ + str(len(collections)) + """
- Themes: """ + str(len(theme_links)) + """

**Pages created/updated**:
- wiki/index.md
- wiki/log.md
"""
    }


class ExtractBuildingWikiPages(Node):
    def prep(self, shared):
        docs = shared["docling_documents"]
        schema_path = Path(shared.get("schema_path", "schema/BUILDING_WIKI.md"))
        schema = schema_path.read_text(encoding="utf-8") if schema_path.exists() else ""
        abstractions = shared.get("abstractions", [])
        relationships = shared.get("relationships", {})
        return docs, schema, abstractions, relationships, shared.get("use_cache", False)

    def exec(self, prep_res):
        docs, schema, abstractions, relationships, use_cache = prep_res
        print("Extracting building/place wiki pages using LLM...")

        entity_plan = extract_entity_plan(docs, schema, abstractions, relationships, use_cache)
        return build_wiki_payload(docs, entity_plan, abstractions, relationships)

    def post(self, shared, prep_res, exec_res):
        shared["wiki_payload"] = exec_res


class WriteBuildingWiki(Node):
    def prep(self, shared):
        return shared["wiki_payload"]

    def exec(self, payload):
        print("Writing wiki pages...")
        written = []

        for item in payload.get("files", []):
            rel = item.get("path", "")
            content = item.get("content", "")
            if not rel.startswith("wiki/"):
                raise ValueError(f"Refusing to write outside wiki/: {rel}")
            if not content.strip():
                raise ValueError(f"Refusing to write empty wiki page: {rel}")
            path = Path(rel)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.name == "log.md" and path.exists():
                if not path.read_text(encoding="utf-8").lstrip().startswith("# "):
                    path.write_text("# Building Memex Wiki Log\n\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                path.write_text(content, encoding="utf-8")
            written.append(str(path))
            print(f"wrote {path}")

        log_append = payload.get("log_append", "").strip()
        if log_append:
            log_path = Path("wiki/log.md")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            if not log_path.exists():
                log_path.write_text("# Building Memex Wiki Log\n", encoding="utf-8")
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write("\n" + log_append + "\n")
            written.append(str(log_path))
            print(f"updated {log_path}")

        return written

    def post(self, shared, prep_res, exec_res):
        shared["wiki_files_written"] = exec_res
