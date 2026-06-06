#!/usr/bin/env python3
from pathlib import Path
import json
import re
import argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="raw/docling-json")
    ap.add_argument("--out", default="output/picture_location_diagram_inventory.tsv")
    args = ap.parse_args()

    raw = Path(args.raw_dir)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    loc_terms = re.compile(
        r"\b(place|location|address|street|road|lane|church|chapel|castle|house|grid|coordinate|postcode)\b",
        re.I,
    )
    diagram_terms = re.compile(
        r"\b(diagram|map|plan|floorplan|floor plan|site plan|chart|table|graph|schematic|drawing|layout)\b",
        re.I,
    )

    lines = ["file\tpicture\tpage\tlocation\tdiagram\tplace\tclass\tcaption"]

    for p in sorted(raw.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue

        texts = {
            t.get("self_ref"): t.get("text", "")
            for t in d.get("texts", [])
            if isinstance(t, dict)
        }

        for i, pic in enumerate(d.get("pictures", []) or []):
            meta = pic.get("meta") or {}
            prov = (pic.get("prov") or [{}])[0]
            page = prov.get("page_no", "")

            captions = []
            for c in pic.get("captions") or []:
                ref = c.get("$ref") if isinstance(c, dict) else None
                if ref in texts:
                    captions.append(texts[ref])

            anns = [
                str(a.get("text") or a.get("description") or "")
                for a in pic.get("annotations") or []
                if isinstance(a, dict)
            ]

            blob = " ".join([str(meta), " ".join(captions), " ".join(anns)])
            has_location = bool(loc_terms.search(blob))
            has_diagram = bool(diagram_terms.search(blob)) or str(
                meta.get("picture_classification", "")
            ).lower() in {"map", "table_chart", "diagram", "chart", "plan"}

            if has_location or has_diagram:
                lines.append("\t".join(map(str, [
                    p.name,
                    f"picture_{i}",
                    page,
                    int(has_location),
                    int(has_diagram),
                    str(meta.get("place") or "")[:80],
                    str(meta.get("picture_classification") or "")[:40],
                    " | ".join(captions)[:160],
                ])))

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote: {out}")
    print(f"rows: {len(lines) - 1}")

if __name__ == "__main__":
    main()
