"""Typer CLI for myblog backend."""
from __future__ import annotations

import asyncio
from datetime import date

import typer
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import Account, Project, SiteMeta, Tag
from app.services.auth import hash_password

app = typer.Typer(no_args_is_help=True, add_completion=False)
seed_app = typer.Typer(no_args_is_help=True)
app.add_typer(seed_app, name="seed")


# No default seed content. Tags are user-created in admin; projects come from
# the GitHub integration sync. The bootstrap seeder still creates the
# site_meta singleton row but with empty content fields so the operator fills
# real values via the admin UI.
DEFAULT_TAGS: list[dict] = []
DEFAULT_PROJECTS: list[tuple] = []


async def _seed_admin(email: str, password: str) -> None:
    async with AsyncSessionLocal() as s:
        existing = (await s.execute(select(Account).limit(1))).scalar_one_or_none()
        if existing is not None:
            existing.email = email
            existing.password_hash = hash_password(password)
            existing.tfa_enabled = False
        else:
            s.add(Account(id=1, email=email, password_hash=hash_password(password)))
        await s.commit()


@seed_app.command("admin")
def seed_admin(
    email: str = typer.Option(..., "--email"),
    password: str = typer.Option(
        ...,
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=False,
    ),
) -> None:
    """Create or update the singleton admin account."""
    asyncio.run(_seed_admin(email, password))
    typer.echo(f"✓ admin account ready: {email}")


async def _seed_bootstrap() -> None:
    async with AsyncSessionLocal() as s:
        # tags
        tags_by_slug: dict[str, Tag] = {}
        for i, td in enumerate(DEFAULT_TAGS):
            existing = (
                await s.execute(select(Tag).where(Tag.slug == td["slug"]))
            ).scalar_one_or_none()
            if existing is None:
                tag = Tag(
                    slug=td["slug"], name=td["name"], color=td["color"], sort_order=i
                )
                s.add(tag)
                await s.flush()
                tags_by_slug[td["slug"]] = tag
            else:
                tags_by_slug[td["slug"]] = existing

        # site_meta singleton
        sm = (
            await s.execute(select(SiteMeta).where(SiteMeta.id == 1))
        ).scalar_one_or_none()
        if sm is None:
            sm = SiteMeta(id=1, handle="admin", launched_at=date.today())
            s.add(sm)

        # projects
        for i, (n, d, lng, st, status) in enumerate(DEFAULT_PROJECTS):
            existing_p = (
                await s.execute(select(Project).where(Project.name == n))
            ).scalar_one_or_none()
            if existing_p is None:
                s.add(
                    Project(
                        name=n,
                        description=d,
                        lang=lng,
                        stars=st,
                        status=status,
                        sort_order=i,
                    )
                )

        await s.commit()


@seed_app.command("bootstrap")
def seed_bootstrap() -> None:
    """Seed default tags, site_meta, and projects."""
    asyncio.run(_seed_bootstrap())
    typer.echo("✓ tags + site_meta + projects seeded")


# ---------------------------------------------------------------------------
# import-md
# ---------------------------------------------------------------------------

from pathlib import Path  # noqa: E402

from app.services.post_ingest import (  # noqa: E402
    IngestError,
    is_sensitive,
    parse_or_infer_frontmatter,
    upsert_post,
)


async def _import_md_file(
    path: Path, default_tag: str | None, overwrite: bool, dry_run: bool
) -> tuple[bool, str]:
    if is_sensitive(path):
        return False, f"⊘ skipped (sensitive name): {path.name}"
    raw = path.read_text(encoding="utf-8")
    async with AsyncSessionLocal() as session:
        try:
            fm_obj, body = await parse_or_infer_frontmatter(
                session, raw=raw, file_path=path, default_tag=default_tag
            )
            if dry_run:
                return (
                    True,
                    f"DRY  {path.name} → id='{fm_obj.id}' tag='{fm_obj.tag}' lang='{fm_obj.lang}'",
                )
            await upsert_post(session, fm=fm_obj, body_md=body, overwrite=overwrite)
            await session.commit()
            return True, f"✓    {path.name} → posts/{fm_obj.id}"
        except IngestError as e:
            return False, f"✗    {path.name} → {e}"


async def _run_imports(
    files: list[Path], default_tag: str | None, overwrite: bool, dry_run: bool
) -> list[tuple[bool, str]]:
    return [await _import_md_file(p, default_tag, overwrite, dry_run) for p in files]


@app.command("import-md")
def import_md(
    path: Path = typer.Argument(..., exists=True, dir_okay=True, file_okay=True),
    overwrite: bool = typer.Option(False, "--overwrite"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    default_tag: str | None = typer.Option(None, "--default-tag"),
) -> None:
    """Import a single .md file or a directory of .md files."""
    files: list[Path] = sorted(path.rglob("*.md")) if path.is_dir() else [path]
    if not files:
        typer.echo("no .md files found")
        raise typer.Exit(code=1)

    results = asyncio.run(_run_imports(files, default_tag, overwrite, dry_run))
    ok = sum(1 for r in results if r[0])
    failed = len(results) - ok
    for _, msg in results:
        typer.echo(msg)
    typer.echo("─" * 60)
    typer.echo(f"total {len(results)} · ok {ok} · failed {failed}")

    # Recompute word counts asynchronously to keep the import path fast
    try:
        asyncio.run(_enqueue_recompute())
    except Exception as e:  # noqa: BLE001
        typer.echo(f"  · recompute enqueue failed (non-fatal): {e}")


async def _enqueue_recompute() -> None:
    from app.workers.queue import enqueue
    await enqueue("recompute_post_word_counts")


if __name__ == "__main__":
    app()
