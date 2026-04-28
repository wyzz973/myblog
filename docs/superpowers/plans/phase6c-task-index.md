# Phase 6c — Task Index & Agent Assignment

Orchestration index for parallel execution of the P6c plan
(`docs/superpowers/plans/2026-04-28-phase6c-danger.md`).

The controller (Claude Code main session) is supervisor — assigns,
reviews, routes bugs, merges. All dev/qa agents use opus (1M context).

## Dependency graph

```
[dev-fdn: 1, 2]
       │
       ▼
   ┌───┴───┬─────────────┐
   ▼       ▼             ▼
[dev-svc][dev-wiper][dev-builder]   ← Wave 1 parallel (file-isolated)
  (3)     (4)         (5)
   │       │           │
   └───┬───┴───────────┘
       ▼
[dev-arq: 6, 7]      ← needs danger svc + export_builder
       │
       ▼
[dev-routes: 8, 9, 10]  ← needs ARQ task registered (task 8 test runs ARQ inline)
       │
       ▼
[dev-closeout: 11, 12, 13]
       │
       ▼
[qa-tester verify]
       │
       ▼
[merge to main]
```

## Lanes

| Lane | Agent ID | Worktree / Branch | Tasks | Files (own) |
|---|---|---|---|---|
| Foundation | `dev-fdn-c` | main worktree on `phase6c-danger` | 1, 2 | `alembic/0007`, `app/models/export_job.py`, `app/models/__init__.py`, `app/models/site_meta.py`, `app/schemas/danger.py` |
| Service | `dev-svc-c` | `phase6c-svc` | 3 | `app/services/danger.py`, `tests/test_danger_service.py` |
| Wiper | `dev-wiper-c` | `phase6c-wiper` | 4 | `app/services/site_wiper.py`, `tests/test_site_wiper.py` |
| Builder | `dev-builder-c` | `phase6c-builder` | 5 | `app/services/export_builder.py`, `tests/test_export_builder.py` |
| ARQ | `dev-arq-c` | main worktree | 6, 7 | `app/workers/tasks/danger.py`, `app/workers/tasks/__init__.py`, `app/workers/runner.py`, `tests/conftest.py`, `tests/test_workers_runner.py`, `tests/test_danger_tasks.py` |
| Routes | `dev-routes-c` | main worktree | 8, 9, 10 | `app/routers/admin/danger.py`, `app/routers/admin/__init__.py`, `tests/test_admin_danger.py` |
| Closeout | `dev-closeout-c` | main worktree | 11, 12, 13 | `tests/test_alembic_0007_roundtrip.py`, possibly `tests/test_alembic_0006_roundtrip.py` |
| QA | `qa-tester-c` | main worktree | verify + bug routing | (read-only) |

## Bug routing protocol

Same as P6b: QA → controller → SendMessage to relevant dev agent (with file:line + repro). Dev fixes + commits a `fix(phase6c):` commit on the appropriate branch. QA re-verifies.

## Commit protocol

- Every task ends with a git commit (per the plan's TDD checklist).
- Commit messages: `feat(phase6c): <component>` or `fix(phase6c): <issue>`.
- Standard Co-Authored-By footer.
- Lane merges: `git checkout phase6c-danger && git merge --no-ff <lane>`.

## Key dependencies

- Wave 1 (svc/wiper/builder) waits on Foundation merge.
- ARQ lane waits on all 3 wave-1 lanes merging back (because task 6's task imports `export_builder.build_export_zip` and `site_wiper.wipe_site_content`, and task 3's `danger.request_export` enqueues `build_export_task`).
- Routes lane waits on ARQ lane merge (task 8's test for `POST /danger/export` runs the ARQ task inline and asserts `status="done"`).
- Closeout waits on Routes lane.
