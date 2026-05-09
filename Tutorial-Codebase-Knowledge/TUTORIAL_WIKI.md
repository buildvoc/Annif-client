# Tutorial Codebase Wiki

A structured, interlinked tutorial knowledge base for a codebase.

## Purpose

This wiki explains a software project for beginners. The AI maintains tutorial pages. The human provides source code, selects repositories/directories, and reviews generated explanations.

## Folder structure

raw/             -- immutable source snapshots, uploaded files, repo manifests
wiki/            -- maintained markdown tutorial/concept pages
wiki/index.md    -- table of contents
wiki/log.md      -- append-only operation log
output/          -- generated complete tutorials, HTML, PDF

## Ingest workflow

When a repo, local directory, or uploaded files are added:

1. Read the selected source files.
2. Identify key abstractions, entry points, data flow, config, and outputs.
3. Create or update concept pages in `wiki/`.
4. Create tutorial chapter pages in beginner-friendly order.
5. Add wiki-links like [[repository-crawler]], [[llm-call-layer]], [[streamlit-ui]].
6. Update `wiki/index.md` with each page and one-line purpose.
7. Append to `wiki/log.md` with date, source, model, and changes.

## Page format

Every page should use:

# Page Title

**Summary**: One to two sentences.

**Sources**:
- path/to/source.py
- path/to/README.md

**Last updated**: YYYY-MM-DD

---

## Beginner explanation

Plain-language explanation.

## How it works

Step-by-step flow.

## Important files

- `file.py` -- what it does

## Related pages

- [[related-page]]

## Rules

- Prefer beginner-friendly explanations.
- Keep code blocks under 10 lines.
- Link related concepts throughout.
- Mark uncertain claims as Needs verification.
- Cite implementation claims with source file paths.
