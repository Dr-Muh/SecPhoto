"""Private command channel and its slash commands."""
from telethon.utils import get_peer_id

from . import config
from .archive import adopt_archive, create_or_sync_archive
from .chats import create_private_channel
from .export import DEFAULT_LIMIT, export_chat


async def get_command_channel(client, state):
    if config.command_channel_id:
        return await client.get_entity(int(config.command_channel_id))

    saved_id = state.data.get("command_channel_id")
    if saved_id:
        try:
            return await client.get_entity(int(saved_id))
        except Exception:
            print("Saved command channel is unavailable; creating a new one")

    channel = await create_private_channel(
        client,
        "SecPhoto Commands",
        "Private command channel for SecPhoto chat archives.",
    )
    state.data["command_channel_id"] = get_peer_id(channel)
    state.save()
    print(f"Created private command channel: {get_peer_id(channel)}")
    return channel


async def list_chats(app, name_filter):
    """Send IDs and display names of all dialogs, optionally filtered by name."""
    needle = name_filter.lower()
    lines = []
    async for dialog in app.client.iter_dialogs():
        if needle and needle not in (dialog.name or "").lower():
            continue
        if dialog.is_channel and not dialog.is_group:
            kind = "channel"
        elif dialog.is_group:
            kind = "group"
        else:
            kind = "user"
        lines.append(f"{dialog.id} [{kind}] {dialog.name}")

    if not lines:
        await app.notify(f"No chats match '{name_filter}'." if name_filter else "No chats found.")
        return

    await app.notify_lines(f"{len(lines)} chat{'s' if len(lines) != 1 else ''}:", lines)


HELP_TEXT = f"""SecPhoto commands:
/help - show this message
/chats [filter] - list chat IDs and names, optionally filtered by name
/export <chat> [limit] - export recent messages to a Markdown file (default limit {DEFAULT_LIMIT})
/archive <chat> [--copy] - create or sync an archive channel for a chat; --copy re-sends messages instead of forwarding them
/archive-adopt <archive> <source> - adopt an existing archive channel for a source chat
/archive-status - show the current archive configuration
/archive-stop - stop live archive mirroring"""


async def handle_command(app, event):
    command = (event.raw_text or "").strip()
    if command == "/help":
        await app.notify(HELP_TEXT)
    elif command == "/chats" or command.startswith("/chats "):
        try:
            await list_chats(app, command[len("/chats"):].strip())
        except Exception as e:
            await app.report_error(f"Listing chats failed: {str(e)}")
    elif command == "/export" or command.startswith("/export "):
        args = command.split()[1:]
        if not 1 <= len(args) <= 2 or (len(args) == 2 and not args[1].isdigit()):
            await app.notify(f"Usage: /export <chat> [limit], default limit is {DEFAULT_LIMIT}.")
            return
        limit = int(args[1]) if len(args) == 2 else DEFAULT_LIMIT
        try:
            await export_chat(app, args[0], limit)
        except Exception as e:
            await app.report_error(f"Export failed: {str(e)}")
    elif command in ("/archive", "/archive-adopt"):
        usage = "/archive <chat> [--copy]" if command == "/archive" else "/archive-adopt <archive> <source>"
        await app.notify(f"Usage: {usage}")
    elif command.startswith("/archive "):
        try:
            args = command.split()[1:]
            # Some Telegram clients turn "--" into an em dash.
            copy_flags = ("--copy", "\u2014copy")
            copy_mode = any(arg in copy_flags for arg in args)
            chat_spec = " ".join(arg for arg in args if arg not in copy_flags)
            if not chat_spec:
                await app.notify("Usage: /archive <chat> [--copy]")
                return
            await create_or_sync_archive(app, chat_spec, copy_mode)
        except Exception as e:
            await app.report_error(f"Archive failed: {str(e)}")
    elif command.startswith("/archive-adopt "):
        try:
            archive_spec, source_spec = command.split(None, 2)[1:]
            await adopt_archive(app, archive_spec, source_spec)
            await app.notify(
                "Existing archive adopted. New source messages will be mirrored."
            )
        except Exception as e:
            await app.report_error(f"Adoption failed: {str(e)}")
    elif command == "/archive-status":
        archive = app.state.archive
        if archive:
            mode = "copy" if archive.get("copy_mode") else "forward"
            await app.notify(
                f"Source: {archive['source']}\nArchive channel ID: {archive['archive_id']}\n"
                f"Mode: {mode}\n"
                f"Last source message: {archive.get('last_source_message_id', 0)}"
            )
        else:
            await app.notify("No archive configured. Use /archive <chat>.")
    elif command == "/archive-stop":
        app.state.data.pop("archive", None)
        app.state.save()
        await app.notify("Live archive mirroring stopped.")
    elif command.startswith("/"):
        await app.notify(f"Unknown command: {command.split()[0]}. Send /help for a list of commands.")
