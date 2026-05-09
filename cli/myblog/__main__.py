import typer

app = typer.Typer(
    name="myblog",
    help="Manage your blog — content, pet, deploy, server.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main() -> None:
    """Entrypoint placeholder; subcommands are wired in later tasks."""


if __name__ == "__main__":
    app()
