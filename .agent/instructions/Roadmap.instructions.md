# 🗺️ Development Roadmap — CSRF Shield AI

> **Purpose:** This file defines the development roadmap and milestone targets for the AI assistant to follow throughout implementation.
> **Last Updated:** February 24, 2026

---

## Golden Rules

1. **Always check `.agent/instructions/` files before starting work** — they contain context and conventions
2. **Follow the phase order** — don't skip ahead; each phase builds on the previous
3. **Write tests alongside implementation** — never leave tests for "later"
4. **Commit after each completed task** — small, focused commits with task IDs
5. **Update `spec/Tasks.md`** status symbols as tasks are completed
6. **Refer to `docs/proposal/PROPOSAL.md` v1.2** as the source of truth for design decisions

---

## Phase 1: Foundation (Week 1–2) — 🚩 CURRENT PHASE

**Goal:** Core infrastructure that all other phases depend on.

### Milestone 1: Project Skeleton

- [x] Initialize project with directory structure matching `PROPOSAL.md` §11.1
- [x] Create `requirements.txt`, `setup.py`
- [x] Create config files (`rules.yaml`, `settings.yaml`)
- [x] Set up pytest infrastructure

### Milestone 2: Data Models

- [x] Implement all 4 core dataclasses in `src/input/models.py`
- [x] Ensure models are immutable where appropriate (use `frozen=True`)
- [x] 100% test coverage on models

### Milestone 3: HAR Parser

- [x] Parse HAR 1.2 files → list of `HttpExchange`
- [x] Handle all 3 content types (urlencoded, multipart, JSON)
- [x] Implement `postData.params` fallback
- [x] Test with sample HAR files in `data/sample_har/`

### Milestone 4: Flow Reconstructor

- [x] Group exchanges by session cookie
- [x] Sort chronologically
- [x] Output `SessionFlow` objects

### Milestone 5: Auth Detector

- [x] Implement `detect_auth_mechanism()` with all 5 custom headers _(see PROPOSAL.md §8.4 — `CUSTOM_AUTH_HEADERS`: Authorization, X-API-Key, X-Auth-Token, Api-Key, X-Access-Token)_
- [x] Implement short-circuit path (yields `AnalysisResult` directly)
- [x] Test cookie-only, bearer-only, API-key, mixed, and no-auth cases

### Milestone 6: Synthetic Data Generator

- [ ] Script generates 600 labeled feature vectors (300 vulnerable, 300 protected)
- [ ] Outputs to `data/synthetic/` in CSV format
- [ ] Validated feature distributions

### Milestone 7: CLI Skeleton

- [ ] Implement `src/main.py` with argparse CLI _(Ref: spec/Tasks.md T-161, T-162, T-163)_
- [ ] Add `analyze` subcommand (skeleton — calls pipeline once implemented)
- [ ] Add `train` subcommand (skeleton — calls trainer once implemented)

### ✅ Phase 1 Exit Criteria

- All core models implemented and tested
- HAR parser handles all content types
- Auth detector short-circuits correctly
- Synthetic data available for Phase 3
- CLI skeleton supports `analyze` and `train` subcommands

---

## Phase 2: Static Analysis (Week 3–4)

**Goal:** All 11 CSRF rules implemented and producing `Finding` objects.

### Key Deliverables

- [ ] Token identification (3-tier strategy) _(see PROPOSAL.md §9.3.1 — Tier 1: exact name match, Tier 2: fuzzy keyword match, Tier 3: high-entropy string detection)_
- [ ] All 11 rules in `src/analysis/rules/`
- [ ] Feature extractor (14 features) _(see PROPOSAL.md §9.3.2 for full feature list)_
- [ ] Static analyzer orchestrator
- [ ] Integration test: HAR → parse → static analysis → findings

### ✅ Phase 2 Exit Criteria

- All 11 rules produce correct findings on test data
- Feature extractor generates valid 14-feature vectors
- Integration test passes end-to-end (up to static analysis)

---

## Phase 3: ML Pipeline (Week 5–6)

**Goal:** Trained model meeting accuracy targets.

### Key Deliverables

- [ ] Merged training dataset from all sources
- [ ] Random Forest + XGBoost trained and evaluated
- [ ] Heuristic boost logic
- [ ] Model metrics meet targets (≥80% accuracy, ≥85% recall)
- [ ] Model serialized to `.pkl`

### ✅ Phase 3 Exit Criteria

- Model trained on ≥1,000 samples
- Accuracy ≥80%, Recall ≥85%
- Heuristic boost correctly adjusts probabilities
- Model file saved and loadable

---

## Phase 4: Risk Scoring & Reports (Week 7–8)

**Goal:** Full pipeline from HAR file to risk report.

### Key Deliverables

- [ ] Risk scorer with Base Score + Modifier formula
- [ ] JSON and HTML report generation
- [ ] Remediation recommendations
- [ ] Full end-to-end integration test

### ✅ Phase 4 Exit Criteria

- Scoring formula matches proposal examples exactly
- HTML report is self-contained and presentable
- End-to-end test: HAR → parse → analyze → ML → score → report ✅

---

## Phase 5: Web Dashboard (Week 9)

**Goal:** Browser-based interface for non-CLI users.

### Key Deliverables

- [ ] Flask app with file upload
- [ ] Results visualization
- [ ] Report export

### ✅ Phase 5 Exit Criteria

- User can upload HAR, see results, and download report via browser

---

## Phase 6: Polish (Week 10)

**Goal:** Documentation, testing, and deliverables.

### Key Deliverables

- [ ] ≥80% test coverage
- [ ] User Guide + API Reference
- [ ] Project report, slides, demo video

### ✅ Phase 6 Exit Criteria

- All MUST requirements from `spec/Requirements.md` are implemented
- All deliverables from `docs/PROPOSAL.md` §14 are ready

---

## Quick Reference: Critical Files

| Purpose                  | File                                                           |
| ------------------------ | -------------------------------------------------------------- |
| Source of truth (design) | `docs/proposal/PROPOSAL.md`                                    |
| Defense prep             | `docs/defense/DEFENSE_NOTES.md`                                |
| Architecture details     | `spec/Design.md`                                               |
| Requirements list        | `spec/Requirements.md`                                         |
| Task tracking            | `spec/Tasks.md`                                                |
| Coding standards         | `.agent/instructions/coding_standards.instructions.md`         |
| Git workflow             | `.agent/instructions/git_workflow.instructions.md`             |
| Testing approach         | `.agent/instructions/testing_strategy.instructions.md`         |
| Task completion workflow | `.agent/instructions/task_completion_workflow.instructions.md` |
| Documentation standards  | `.agent/instructions/documentation_standards.instructions.md`  |

---

_Update this roadmap after completing each phase. Check off milestones and adjust timelines as needed._
