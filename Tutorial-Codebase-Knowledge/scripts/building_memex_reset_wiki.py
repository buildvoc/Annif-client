from pathlib import Path
import shutil

wiki = Path("wiki")
if wiki.exists():
    shutil.rmtree(wiki)

for d in ["sources", "buildings", "places", "streets", "collections", "themes"]:
    (wiki / d).mkdir(parents=True, exist_ok=True)

(wiki / "index.md").write_text("# Building Memex Wiki Index\n", encoding="utf-8")
(wiki / "log.md").write_text("# Building Memex Wiki Log\n", encoding="utf-8")

print("reset wiki/")
