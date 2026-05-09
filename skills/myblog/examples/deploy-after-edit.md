# Workflow: Deploy after fixing a bug

User: "刚改了 backend 的 site router，部署一下。"

Agent steps:

```
$ myblog server status
| service        | state    |
| myblog-api     | active   |
| myblog-worker  | active   |
| postgresql     | active   |
| redis-server   | active   |
| nginx          | active   |

$ myblog deploy code
==> rsync code → root@<server>:/opt/myblog/repo
==> uv sync + alembic upgrade head
✓ deploy complete

$ myblog server status        # re-check
| service        | state    |
| myblog-api     | active   |
...
```

If `myblog-api` shows `inactive` after deploy:

```
$ myblog server logs api --tail 200
... exception trace ...
```

Report the exception to the user; do **not** auto-rollback (the user decides).
