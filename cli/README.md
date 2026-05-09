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
