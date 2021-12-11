from __future__ import annotations

import asyncio
import re

import hikari
import lightbulb
import piston_rspy

from carberretta.utils import helpers

plugin = lightbulb.Plugin("Execute", include_datastore=True)
client = piston_rspy.Client()
plugin.d.active_messages = [] # FIXME: probably wont need this


@plugin.command
@lightbulb.option("version", "The version of the language.", default="*")
@lightbulb.option("language", "The programming language to use.")
@lightbulb.command("execute", "Executes arbitrary code from the next message you send.", guilds=(695021594430668882,)) # FIXME: remove dev guild
@lightbulb.implements(lightbulb.SlashCommand)
async def cmd_execute(ctx: lightbulb.SlashContext) -> None:
    language = ctx.options.language
    version = ctx.options.version
    await ctx.respond("Send your source code now")

    if not (src_message := await wait_for_message(ctx)):
        return None

    if not (source := await extract_source(src_message)):
        return None

    resp = await execute_source(language, version, source)
    exec_message = await src_message.respond(
        generate_response(ctx.author, resp), reply=True,
    )

    # TODO: add a stream that allows the user to edit their code and re-runs it.
    # should this allow for changing the language and version? may need to remove
    # those as slash command options and parse them from the message content?


async def wait_for_message(ctx: lightbulb.SlashContext) -> hikari.Message | None:
    try:
        event = await ctx.app.wait_for(
            hikari.GuildMessageCreateEvent,
            timeout=300,
            predicate=lambda e: (
                e.channel_id == ctx.channel_id and e.author_id == ctx.author.id
            )
        )
    except asyncio.TimeoutError:
        await ctx.respond("No source received within 5 minutes, closing listener.")
        return None

    return event.message


async def execute_source(
    language: str, version: str, source: str,
) -> piston_rspy.ExecResponse:
    return await client.execute(
        piston_rspy.Executor(
            language=language,
            version=version,
            files=[piston_rspy.File(content=source)],
        )
    )


async def extract_source(message: hikari.Message) -> str | None:
    matches = re.match(r"```(\w+\s+)?([\w\W]+)[\s+]?```", message.content or "")
    if matches:
        return matches.group(2)

    await message.respond(
        "Invalid source code. Make sure to wrap it in triple backticks.", reply=True,
    )
    return None


def generate_response(
    author: hikari.User, resp: piston_rspy.ExecResponse,
) -> hikari.Embed:
    stdout = resp.run.stdout
    stderr = resp.run.stderr

    if resp.compile:
        stderr = f"{resp.compile.stderr}\n{stderr}"

    e = hikari.Embed(title="Execution result", colour=helpers.choose_colour())
    e.set_footer(
        text=f"Ran {author.username} {resp.language} v{resp.version} code.",
        icon=author.avatar_url or author.default_avatar_url,
    )

    if stderr:
        e.add_field(name="stderr", value=f"```bash\n{stderr}```", inline=False)

    if stdout:
        e.add_field(name="stdout", value=f"```bash\n{stdout}```", inline=False)

    return e


def load(bot: lightbulb.BotApp) -> None:
    bot.add_plugin(plugin)


def unload(bot: lightbulb.BotApp) -> None:
    bot.remove_plugin(plugin)
