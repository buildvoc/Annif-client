## Building Memex Wiki Workflow

This branch includes a DoclingDocument-to-wiki workflow for creating a structured Building Memex from source documents.

### Inputs

- `raw/docling-json/` — immutable DoclingDocument JSON source files.
- `schema/BUILDING_WIKI.md` — wiki page rules and source-backed writing constraints.

### First pass: entity wiki creation

Run the first-pass ingest to create source, building, place, street, collection, and theme pages:

```bash
docker-compose exec -T tutorial-generator bash -lc '
cd /app
PYTHONDONTWRITEBYTECODE=1 python scripts/llm_ingest_building_wiki.py \
  --raw-dir /app/raw/docling-json \
  --schema /app/schema/BUILDING_WIKI.md \
  --no-cache
'
```

The first pass uses the existing Tutorial-Codebase-Knowledge nodes:

1. `FetchDoclingDocuments`
2. `IdentifyAbstractions`
3. `AnalyzeRelationships`
4. `ExtractBuildingWikiPages`
5. `WriteBuildingWiki`

Generated pages are written to:

- `wiki/sources/`
- `wiki/buildings/`
- `wiki/places/`
- `wiki/streets/`
- `wiki/collections/`
- `wiki/themes/`

### Second pass: collection creation

Run the second pass to review existing wiki pages and create/update collections:

```bash
docker-compose exec -T tutorial-generator bash -lc '
cd /app
PYTHONDONTWRITEBYTECODE=1 python scripts/llm_second_pass_collections.py
'
```

The second pass reads existing wiki pages, runs `IdentifyAbstractions` and `AnalyzeRelationships`, then asks Ollama JSON mode to create collection pages using only existing building slugs as members.

### Validation

Check the wiki for broken links and page-format issues:

```bash
python3 - <<'PY'
from pathlib import Path
import re

issues = []
for p in Path("wiki").rglob("*.md"):
    s = p.read_text(encoding="utf-8", errors="replace")
    if not s.strip():
        issues.append((p, "empty file"))
    if not s.lstrip().startswith("# "):
        issues.append((p, "missing H1"))
    for link in re.findall(r"\[\[([^\]]+)\]\]", s):
        if not list(Path("wiki").rglob(link + ".md")):
            issues.append((p, f"broken link [[{link}]]"))

print("issues:", len(issues))
for p, msg in issues[:100]:
    print(f"{p}: {msg}")
PY
```

### Ollama configuration

Set the model in `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma3:4b-it-q4_K_M
```

For remote Ollama, replace `OLLAMA_BASE_URL` with the reachable host, for example:

```env
OLLAMA_BASE_URL=http://192.168.1.178:11434
```

