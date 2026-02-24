# 📝 Documentation Standards

> **Purpose:** Rules for where and how documentation files are organized.
> **Last Updated:** February 24, 2026

---

## Golden Rule

> **All project documentation `.md` files MUST live inside `docs/`.**

### Allowed Exceptions

The following `.md` files are **explicitly allowed** outside `docs/`:

| Location                                | Purpose                     | Why it's exempt                         |
| --------------------------------------- | --------------------------- | --------------------------------------- |
| `README.md` (project root)              | Project overview for GitHub | Convention                              |
| `.agent/instructions/*.instructions.md` | AI agent instruction files  | Operational config, not project docs    |
| `spec/*.md`                             | Design, Requirements, Tasks | Specification files, separate from docs |

### Examples

- ✅ `docs/proposal/PROPOSAL.md`
- ✅ `docs/guides/USER_GUIDE.md`
- ✅ `docs/reports/2026-03-01_phase1-complete.md`
- ✅ `README.md` (project root)
- ✅ `.agent/instructions/Roadmap.instructions.md` (agent config)
- ✅ `spec/Design.md` (specification)
- ❌ `src/NOTES.md` — move to `docs/`
- ❌ `scripts/HOWTO.md` — move to `docs/`
- ❌ `CHANGELOG.md` at project root — move to `docs/`

---

## Folder Structure

All documents are organized into category subfolders inside `docs/`:

```
docs/
├── proposal/       # Project proposal and related formal documents
├── defense/        # Defense preparation materials
├── guides/         # User-facing documentation (User Guide, API Reference)
├── reports/        # Task/milestone completion reports
└── reviews/        # Peer review feedback and external reviews
```

---

## Adding New Documents

### If it fits an existing category → place it there

| Document Type                          | Folder           |
| -------------------------------------- | ---------------- |
| Formal project documents, proposals    | `docs/proposal/` |
| Defense Q&A, presentation prep         | `docs/defense/`  |
| User guides, API references, tutorials | `docs/guides/`   |
| Task/milestone completion reports      | `docs/reports/`  |
| External reviews, feedback             | `docs/reviews/`  |

### If it does NOT fit an existing category → create a new folder

1. Create a new subfolder under `docs/` with a name that reflects the document type
2. Use lowercase, short, descriptive folder names (e.g., `docs/architecture/`, `docs/meeting-notes/`, `docs/research/`)
3. Update the project tree in `docs/proposal/PROPOSAL.md` §11.1 to include the new folder
4. Add a brief `README.md` in the new folder explaining its purpose

**Example:** If you need to store research notes about CSRF techniques:

```
docs/
└── research/
    ├── README.md                    # "Research notes on CSRF techniques"
    ├── csrf-token-patterns.md
    └── samesite-cookie-analysis.md
```

---

## Naming Conventions

| Type         | Pattern                     | Example                             |
| ------------ | --------------------------- | ----------------------------------- |
| Reports      | `YYYY-MM-DD_<name>.md`      | `2026-03-01_phase1-complete.md`     |
| Guides       | `UPPER_CASE.md`             | `USER_GUIDE.md`, `API_REFERENCE.md` |
| General docs | `lowercase-with-hyphens.md` | `csrf-token-patterns.md`            |
| Folder index | `README.md`                 | Always `README.md`                  |

---

## Checklist Before Creating a Document

- [ ] Is this a `.md` file? → It goes in `docs/` (not `src/`, `scripts/`, root, etc.)
- [ ] Does an appropriate subfolder exist?
  - **Yes** → Place it there
  - **No** → Create a new subfolder, add a `README.md`, update §11.1 tree
- [ ] Is the filename following the naming convention above?

---

_No markdown files outside `docs/` unless explicitly whitelisted above (root `README.md`, `.agent/instructions/`, `spec/`)._
