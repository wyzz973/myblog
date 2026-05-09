# Workflow: Tweak pet personality

User: "把 pet 的 chill persona 调得更幽默一点。"

Agent steps:

```
$ myblog pet personality get --json > /tmp/pet-before.json
$ jq .personas.chill /tmp/pet-before.json
{ ... old chill text ... }

# Edit a copy
$ cp /tmp/pet-before.json /tmp/pet-after.json
# (open editor; only modify personas.chill)

$ myblog pet personality set --from-json /tmp/pet-after.json
{"enabled": true, "personas": {...}, "mode_templates": {...}}

# Verify
$ myblog pet personality get --json | jq .personas.chill
{ ... new chill text ... }
```

Rollback (if user dislikes the result):

```
$ myblog pet personality set --from-json /tmp/pet-before.json
```
