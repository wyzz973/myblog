---
name: myblog
description: Manage the MyBlog deployment with the `myblog` CLI — write/publish posts, edit pet personality, upload media, deploy to the server, inspect logs. Trigger words 博客 / blog / myblog / 发文章 / 写博客 / 改 pet / 部署 / 上线 / 服务器日志 / pet 性格.
---

# Using `myblog` to manage the blog

The `myblog` CLI wraps the admin HTTP API of the blog and the SSH-based deploy / server ops. Use it whenever the user wants to:

- write or publish a post
- edit the pet config / personality / species
- upload media (and embed it in a post)
- deploy code or frontend to the server
- restart services / check logs / inspect state

## First-time setup

```bash
uv tool install --editable ./cli   # one-time
myblog auth login                   # paste base_url + admin token
myblog auth whoami                  # confirms token works
```

If `myblog auth whoami` exits non-zero, **stop and tell the user**. Do not try to brute-force token recovery.

## Command map

**Content (HTTP)**
```
myblog site get/set                   # site identity
myblog site theme set --accent X      # accent colors
myblog post list/get/new/edit/        # posts
       publish/unpublish/delete/from-md
myblog tag list/add/rename/delete
myblog media upload/list/rm
myblog pet config get/set
myblog pet personality get/set/reset
myblog pet memory list/get/clear
myblog pet timeline list <visitor>
myblog pet species list/add/edit/rm
myblog projects list/add/set/rm
myblog now list/add/set/rm
```

**Ops (SSH)**
```
myblog deploy full|code|front
myblog server status
myblog server logs api|worker|nginx [--tail N] [--follow]
myblog server restart api|worker
myblog server ssh -- "<remote command>"
myblog server migrate up|status|down <rev>
myblog server backup db|media [--out path]
myblog server shell psql|redis
```

## Workflows (canonical)

### 1. Publish a post from a local Markdown file

1. Validate the file has frontmatter with at least `id`, `title`, `tag`, `date`. If `id` is missing, ask the user before generating one.
2. Dry-run: `myblog post from-md ./my-post.md` (in v1 this actually creates as draft if frontmatter says `status: draft`; otherwise it follows the file).
3. If the user wants it live now: `myblog post publish <returned id>`.
4. Deploy frontend if you bumped any static asset; otherwise no deploy is needed for content.

### 2. Tweak pet personality

1. `myblog pet personality get --json > /tmp/pet-before.json` (back it up).
2. Edit a copy: `cp /tmp/pet-before.json /tmp/pet-after.json` and modify only the keys the user asked about.
3. `myblog pet personality set --from-json /tmp/pet-after.json`.
4. Verify: `myblog pet personality get --json` and diff against `/tmp/pet-before.json`.
5. If the user asked to roll back: `myblog pet personality set --from-json /tmp/pet-before.json`.

### 3. Upload media and embed in a post

1. `myblog media upload ./photo.png --alt "..."`. Capture the returned `url` from the JSON output.
2. Either: edit the post body locally and `myblog post edit <id> --body-file ./post.md`, or instruct the user to insert `![alt](<url>)`.
3. `myblog deploy front` is **not** needed for media — they're served from the backend.

### 4. Deploy after fixing a bug

1. `myblog server status` to confirm services are healthy first.
2. Frontend-only fix: `myblog deploy front`. Backend fix: `myblog deploy code`. Both: `myblog deploy full`.
3. After deploy, `myblog server status` again; if `myblog-api` is not active, `myblog server logs api --tail 200` to read the failure.

## Danger rules — read carefully

These commands are L2: they print a dry-run summary by default and do nothing until you add `--yes`.

- `myblog post delete <id>`
- `myblog tag delete <id>`
- `myblog media rm <id>`
- `myblog pet memory clear <visitor_hash>`
- `myblog pet personality reset personas|templates|both`
- `myblog projects rm <name>`
- `myblog now rm <id>`
- `myblog server restart api|worker`

These are L3 — they require literal `--confirm "I understand"` and should never be run without explicit user authorization in the same conversation:

- `myblog server migrate down <rev>`
- `myblog server backup restore db <file>`

If the user asks for an L3 action, repeat back what will happen, explicitly request confirmation in plain language, and only then run with `--confirm "I understand"`.

## Output flag

For programmatic chaining, append `--json` to any command. Output is ndjson (one object per line). Errors come on stderr also as JSON `{"error": "...", "code": N}`.

## Troubleshooting

- 401 on any HTTP command → `myblog auth whoami` first; ask user for a fresh token if invalid.
- `not configured: .env.deploy not found` → run from inside the MyBlog repo or its subdirectory.
- `sshpass: command not found` → ask the user to `brew install hudochenkov/sshpass/sshpass` (macOS).
- After `myblog deploy full`, if `myblog server status` shows `myblog-api inactive` → check `myblog server logs api --tail 200` for the exception, do not auto-rollback.

## When NOT to use this skill

- Writing or modifying frontend / backend source code → use normal editing tools.
- Anything that touches GitHub releases, issues, or PRs → use `gh`.
- Browser-side testing or screenshotting → use Playwright/Chrome DevTools tools.
- `comments / contacts / integrations / api-tokens / analytics / activity / account / danger` admin areas — those are not in v1 of this CLI; for them, ask the user to use the web admin.
