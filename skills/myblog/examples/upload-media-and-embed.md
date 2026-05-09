# Workflow: Upload media and embed in a post

User: "把 ./hero.png 放进文章 042-cli-launch。"

Agent steps:

```
$ myblog media upload ./hero.png --alt "myblog CLI banner"
{"id": 17, "filename": "hero.png", "url": "/media/2026/05/hero.png", ...}

# Read existing body, append the image, write to a temp file
$ myblog --json post get 042-cli-launch | jq -r .body_md > /tmp/body.md
$ printf '\n\n![myblog CLI banner](/media/2026/05/hero.png)\n' >> /tmp/body.md

$ myblog post edit 042-cli-launch --body-file /tmp/body.md
{"id": "042-cli-launch", ...}
```

No deploy needed — `/media/*` is served by the backend, not the static dist.
