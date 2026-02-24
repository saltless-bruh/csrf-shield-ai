# 🌿 Git Workflow — CSRF Shield AI

> **Purpose:** Define Git branching strategy and commit conventions.
> **Last Updated:** February 24, 2026

---

## 1. Branch Strategy

### 1.1 Branch Naming

| Branch Type | Pattern                          | Example                       |
| ----------- | -------------------------------- | ----------------------------- |
| Main        | `main`                           | Production-ready code         |
| Feature     | `feature/<task-id>-<short-name>` | `feature/T-121-har-parser`    |
| Fix         | `fix/<task-id>-<short-name>`     | `fix/T-124-multipart-parsing` |
| Phase       | `phase/<number>-<name>`          | `phase/1-foundation`          |

### 1.2 Workflow

1. Create a `phase/X-name` branch from `main` for each dev phase
2. Create `feature/T-xxx-name` branches from the phase branch for individual tasks
3. Merge feature branches into phase branch via `git merge --no-ff` (preserves merge commit for traceability)
4. Merge phase branch into `main` when phase exit criteria are met
5. Tag releases: `v0.1.0` (Phase 1), `v0.2.0` (Phase 2), etc.

> **Note:** Pull Requests are optional and require manual GitHub CLI/web setup. The default workflow uses local `git merge --no-ff` operations.

---

## 2. Commit Conventions

### 2.1 Format

```
<type>(<scope>): <description>

[optional body]

[optional footer: Refs: T-xxx]
```

### 2.2 Types

| Type       | Meaning            | Example                                          |
| ---------- | ------------------ | ------------------------------------------------ |
| `feat`     | New feature        | `feat(parser): implement HAR 1.2 file parsing`   |
| `fix`      | Bug fix            | `fix(auth): detect X-API-Key in custom headers`  |
| `test`     | Tests              | `test(parser): add multipart body parsing tests` |
| `docs`     | Documentation      | `docs: update PROPOSAL.md to v1.2`               |
| `refactor` | Code restructuring | `refactor(models): use frozen dataclasses`       |
| `chore`    | Maintenance        | `chore: update requirements.txt`                 |
| `style`    | Formatting         | `style: apply black formatting`                  |

### 2.3 Rules

- Keep subject line under 72 characters
- Use imperative mood: "add feature" not "added feature"
- Reference task IDs in footer: `Refs: T-121, T-122`
- One logical change per commit
- Never commit broken code to `main`

---

## 3. Example Commit Sequence (Phase 1)

```
feat(models): implement HttpExchange and SessionFlow dataclasses
Refs: T-111, T-112

test(models): add unit tests for all core data models
Refs: T-115

feat(parser): implement HAR 1.2 file parser with content type handling
Refs: T-121, T-122, T-123, T-124, T-125

test(parser): add HAR parser tests for all content types
Refs: T-127

feat(auth): implement auth mechanism detection with custom headers
Refs: T-141, T-142, T-143

feat(synth): implement synthetic training data generator
Refs: T-151, T-152, T-153
```

---

_Consistent commits make the project history readable and help the supervisor trace feature implementation._
