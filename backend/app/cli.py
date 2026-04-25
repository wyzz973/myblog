"""Typer CLI for myblog backend."""
from __future__ import annotations

import asyncio

import typer
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import Account
from app.services.auth import hash_password

app = typer.Typer(no_args_is_help=True, add_completion=False)
seed_app = typer.Typer(no_args_is_help=True)
app.add_typer(seed_app, name="seed")


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


if __name__ == "__main__":
    app()
