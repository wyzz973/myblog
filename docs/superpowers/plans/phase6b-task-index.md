# Phase 6b — Task Index & Agent Assignment

This is the orchestration index for parallel execution of the P6b plan
(`docs/superpowers/plans/2026-04-28-phase6b-analytics.md`).

The controller (Claude Code main session) acts as supervisor — assigns tasks,
reviews, routes bugs, merges lanes. All dev/qa agents use opus (1M context).

## Lanes

| Lane | Agent ID | Branch / Worktree | Tasks | Files (own) |
|---|---|---|---|---|
| Foundation | `dev-fdn` | `phase6b-analytics` (main worktree) | 1, 2, 3 | `alembic/versions/0006`, `app/models/hit_*`, `app/models/__init__.py`, `app/schemas/analytics.py` |
| Write | `dev-write` | `phase6b-write` worktree | 4, 5 | `app/services/hits.py`, `app/routers/public/hits.py`, `app/routers/public/__init__.py`, `tests/test_hits_service.py`, `tests/test_public_hits.py` |
| Rollup | `dev-rollup` | `phase6b-rollup` worktree | 6 | `app/workers/tasks/analytics.py`, `app/workers/tasks/__init__.py`, `app/workers/runner.py`, `tests/conftest.py`, `tests/test_analytics_rollup.py` |
| Read | `dev-read` | `phase6b-read` worktree | 7, 8, 9, 10, 11, 12 | `app/services/analytics.py`, `app/routers/admin/analytics.py`, `app/routers/admin/__init__.py`, `tests/test_analytics_service.py`, `tests/test_admin_analytics.py` |
| Closeout | `dev-closeout` | `phase6b-analytics` (after merges) | 13, 14 | `tests/test_alembic_0006_roundtrip.py` |
| QA | `qa-tester` | (any) | verification + bug routing | (read-only against each lane's branch) |

## Sequencing

```
[Foundation: 1→2→3]
        │
        ├─► merge into phase6b-analytics
        │
        ├─► [Write: 4→5]      ┐
        ├─► [Rollup: 6]       ├─► parallel after foundation
        └─► [Read: 7→8→9→10→11→12]  ┘
                              │
                              ▼ (each lane completes)
                         [QA verifies branch]
                              │
                              ▼ (clean)
                       merge into phase6b-analytics
                              │
                              ▼ (all 3 lanes merged)
                       [Closeout: 13→14]
                              │
                              ▼
                       [QA final verify]
                              │
                              ▼
                       merge to main
```

## Bug routing protocol

When QA finds a bug:
1. QA produces a structured report: file:line, repro steps, expected vs actual.
2. QA returns the report to the controller (does NOT fix).
3. Controller reads the report and re-engages the relevant dev via SendMessage,
   pasting the bug details + asking for a targeted fix.
4. Dev fixes + commits a `fix(phase6b):` commit on their lane's branch.
5. QA re-runs.
6. Loop until clean.

## Commit protocol

- Every task ends with a git commit (per the plan's TDD checklist Step 5).
- Commit messages: `feat(phase6b): <component>` or `fix(phase6b): <issue>`.
- All commits include the standard Co-Authored-By footer.
- Lane merges: `git checkout phase6b-analytics && git merge --no-ff phase6b-<lane>`.

## Dependencies

- **Foundation must complete first**. ORM (HitEvent, HitDaily) and schemas
  (HitRequest, etc.) are imported by all three lanes.
- Lanes A/B/C are **mutually independent** by file ownership — no merge conflicts expected.
- **Tests share one Postgres**: parallel `pytest` runs across worktrees would
  race on shared tables. QA runs are serialized by the controller.

## State tracking

Controller maintains live status via TaskList. Lane status:
- `pending` — not yet dispatched
- `in_progress` — agent running
- `qa_review` — agent finished, qa verifying
- `bug_routing` — qa found issue, dev fixing
- `merged` — branch merged into phase6b-analytics
- `done` — merged to main
