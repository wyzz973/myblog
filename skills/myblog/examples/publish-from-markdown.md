# Workflow: Publish a post from a local Markdown file

User: "发一篇博客，文件在 /tmp/new-post.md。"

Agent steps:

```
$ head -10 /tmp/new-post.md
---
id: 042-cli-launch
n: "042"
title: "Launching the myblog CLI"
tag: notes
date: 2026-05-09
---

The CLI is finally here.

$ myblog post from-md /tmp/new-post.md
{"id": "042-cli-launch", "title": "Launching the myblog CLI", "status": "draft", ...}

$ myblog post publish 042-cli-launch
{"id": "042-cli-launch", "status": "published", ...}
```

Then: confirm by visiting `https://<your-domain>/p/042-cli-launch` (offer the link to the user — do not auto-open).
