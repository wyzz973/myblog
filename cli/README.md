# myblog CLI

Manage the blog from the terminal. See
`docs/superpowers/specs/2026-05-09-myblog-cli-and-skill-design.md`
for the full design.

## Install (editable, recommended for development)

    uv tool install --editable ./cli

## First run

    myblog auth login           # paste base_url + admin token
    myblog auth whoami          # confirm
    myblog skill install        # register skill with Claude Code

## Troubleshooting

- **`myblog auth whoami` returns 401** — token expired or wrong; re-run `myblog auth login`.
- **`sshpass: command not found`** — `brew install hudochenkov/sshpass/sshpass` on macOS.
- **`scripts/deploy.sh: not found`** — make sure you're inside the MyBlog repo (CLI walks up to find `.env.deploy` and `scripts/deploy.sh`).
- **Skill not picked up by Claude Code** — verify with `myblog skill status` that `user_installed=true`. If yes, restart Claude Code so it re-scans `~/.claude/skills/`.

## Secret-leak guard (run before pushing)

Production code, README, pyproject, and skills must not contain real IPs / tokens / passwords / SSH hosts. Test files use deliberate placeholders (`secret`, `super-secret-token`) and are excluded.

```bash
git ls-files cli/myblog/ cli/README.md cli/pyproject.toml skills/ \
  | xargs grep -nE '\b(8|10|172|192)\.[0-9]+\.[0-9]+\.[0-9]+\b|cfut_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|wyzz973' \
  || echo "no leaks"
```

Expected: `no leaks`. Real secrets live only in `~/.config/myblog/credentials.toml` and `.env.deploy` (both gitignored).
