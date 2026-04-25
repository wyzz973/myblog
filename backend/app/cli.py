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


DEFAULT_TAGS = [
    {"slug": "backend", "name": "backend", "color": "#7aa7ff"},
    {"slug": "ai", "name": "ai", "color": "#b794ff"},
    {"slug": "ml", "name": "ml", "color": "#ffb86b"},
    {"slug": "devtools", "name": "devtools", "color": "#7dd3a4"},
    {"slug": "infra", "name": "infra", "color": "#f47174"},
]

DEFAULT_PROJECTS = [
    (
        "segformer-lite",
        "Tiny, quant-friendly segmentation model. 3.2MB, runs on ESP32-S3.",
        "Python",
        1240,
        "active",
    ),
    (
        "agentkit-jvm",
        "LangChain-style agent primitives, native Java. Zero Python in prod.",
        "Java",
        812,
        "active",
    ),
    (
        "pghelper-debug",
        "Runtime diagnostic for PageHelper — tells you why your page didn't page.",
        "Java",
        203,
        "maintained",
    ),
    (
        "dotfiles",
        "Terminal, editor, and kernel tunings I run on every box.",
        "Shell",
        96,
        "active",
    ),
    (
        "term-i18n",
        "Lint your SSH/locale config across a fleet. Catches the Termius bug at scale.",
        "Go",
        61,
        "active",
    ),
]


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
            sm = SiteMeta(
                id=1,
                handle="wangyang",
                name="汪洋",
                name_en="Wang Yang",
                role="Backend / AI Full-Stack Engineer",
                tagline="Backends that don't flinch. Models that ship.",
                bio="I build backend systems and AI agents.",
                location="Hangzhou, CN",
                email="hi@wangyang.dev",
                github="wangyang",
                typing_line=(
                    "// building backends that don't flinch.\n"
                    "// training models that ship."
                ),
                stack_chips=["Java", "Python", "PyTorch", "Agents", "Segmentation"],
                footer_note="© 2026 Wang Yang · hand-coded · cookie-less analytics",
                launched_at=date(2023, 1, 1),
            )
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


if __name__ == "__main__":
    app()
