import typer

from myblog import output
from myblog.commands import auth as auth_cmd
from myblog.commands import deploy as deploy_cmd
from myblog.commands import media as media_cmd
from myblog.commands import now as now_cmd
from myblog.commands import pet as pet_cmd
from myblog.commands import post as post_cmd
from myblog.commands import projects as projects_cmd
from myblog.commands import server as server_cmd
from myblog.commands import site as site_cmd
from myblog.commands import skill as skill_cmd
from myblog.commands import tag as tag_cmd

app = typer.Typer(
    name="myblog",
    help="Manage your blog — content, pet, deploy, server.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Emit ndjson on stdout (one object per line) and ndjson errors on stderr.",
    ),
) -> None:
    output.set_format(json_mode=json_mode)


app.add_typer(auth_cmd.app, name="auth")
app.add_typer(site_cmd.app, name="site")
app.add_typer(post_cmd.app, name="post")
app.add_typer(tag_cmd.app, name="tag")
app.add_typer(media_cmd.app, name="media")
app.add_typer(pet_cmd.app, name="pet")
app.add_typer(projects_cmd.app, name="projects")
app.add_typer(now_cmd.app, name="now")
app.add_typer(deploy_cmd.app, name="deploy")
app.add_typer(server_cmd.app, name="server")
app.add_typer(skill_cmd.app, name="skill")

if __name__ == "__main__":
    app()
