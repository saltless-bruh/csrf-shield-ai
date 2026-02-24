# 🔄 Task Completion Workflow

> **Purpose:** Defines the mandatory workflow to follow when working on, completing, and reporting tasks.
> **Last Updated:** February 24, 2026

---

## Before Starting a Task

1. **Check `spec/Tasks.md`** — Find the task by its `T-xxx` ID. Read its description, requirement reference (`FR-xxx`), and dependencies.
2. **Check `spec/Requirements.md`** — Look up the referenced `FR-xxx` / `NFR-xxx` requirement for full acceptance criteria, priority, and phase.
3. **Check `spec/Design.md`** — If the task involves a data model or architectural decision, review the relevant design section.
4. **Check this instruction file** — Ensure you understand the full completion workflow below.

---

## During Development

- Follow `.agent/instructions/coding_standards.instructions.md` for code style
- Follow `.agent/instructions/git_workflow.instructions.md` for commits
- Follow `.agent/instructions/testing_strategy.instructions.md` for test expectations
- Write tests **alongside** implementation, never defer them

---

## After Completing a Task

### Step 1: Update Tracking Documents

Update **both** of these files by changing `[ ]` to `[x]` for the completed task:

- **`.agent/instructions/Roadmap.instructions.md`** — Check off the completed milestone item
- **`spec/Tasks.md`** — Change the status symbol from `⬜` to `✅` for the completed `T-xxx` task

### Step 2: Cross-Check for Missing Features

After finishing a task or milestone, **compare the tracking documents against the actual codebase**:

1. Read through `spec/Tasks.md` for tasks marked as `✅` (completed)
2. For each completed task, verify the corresponding code **actually exists and works**
3. Check for any tasks that should have been completed as part of the current milestone but were missed

**If a "completed" task is actually missing or incomplete:**

- Change its status back to `⬜` or `🔵` (in progress)
- **Start working on it immediately** — do not leave it for later

**If a planned feature was deemed unnecessary during development:**

- Change its status to `🔄` (Needs revision) in `spec/Tasks.md`
- Add a note explaining why it was removed or deferred
- Update `Roadmap.instructions.md` accordingly with a note

### Step 3: Create a Completion Report

After all verification is done, create a report in `docs/reports/` with the following naming convention:

```
docs/reports/YYYY-MM-DD_<milestone-or-task-name>.md
```

**Example filenames:**

- `docs/reports/2026-02-25_phase1-project-setup.md`
- `docs/reports/2026-03-01_milestone2-data-models.md`
- `docs/reports/2026-03-05_T-121-har-parser.md`

**Report template:**

```markdown
# [Task/Milestone Name] — Completion Report

> **Date:** YYYY-MM-DD
> **Phase:** Phase X
> **Task IDs:** T-xxx, T-xxx, ...
> **Requirement IDs:** FR-xxx, FR-xxx, ...

---

## Summary

Brief description of what was accomplished.

## Changes Made

- List of files created/modified
- Key implementation decisions

## Tests

- Tests written and their status (pass/fail)
- Coverage for the implemented module

## Cross-Check Results

- [ ] All related tasks in `spec/Tasks.md` verified against codebase
- [ ] `Roadmap.instructions.md` updated
- [ ] `spec/Tasks.md` statuses updated
- [ ] No missing features found (or: list of missing features addressed)

## Issues / Notes

Any blockers, deferred items, or design changes discovered during implementation.

## Next Steps

What should be worked on next, based on the task dependency graph.
```

---

## Quick Checklist (Copy-Paste for Each Task)

```
Before:
- [ ] Read task in spec/Tasks.md
- [ ] Read requirement in spec/Requirements.md
- [ ] Check design in spec/Design.md (if relevant)

After:
- [ ] Code implemented and working
- [ ] Tests written and passing
- [ ] Roadmap.instructions.md updated ([ ] → [x])
- [ ] spec/Tasks.md updated (⬜ → ✅)
- [ ] Cross-checked codebase vs. tracking docs
- [ ] Missing features addressed (if any)
- [ ] Completion report created in docs/reports/
```

---

_This workflow is mandatory for every task. No exceptions._
