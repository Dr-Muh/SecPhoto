"""Private command channel and its slash commands."""
from telethon.utils import get_peer_id

from . import config
from .archive import adopt_archive, create_or_sync_archive
from .chats import create_private_channel


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


async def handle_command(app, event):
    command = (event.raw_text or "").strip()
    if command == "/chats" or command.startswith("/chats "):
        try:
            await list_chats(app, command[len("/chats"):].strip())
        except Exception as e:
            await app.report_error(f"Listing chats failed: {str(e)}")
    elif command.startswith("/archive "):
        try:
            await create_or_sync_archive(app, command.split(None, 1)[1].strip())
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
            await app.notify(
                f"Source: {archive['source']}\nArchive channel ID: {archive['archive_id']}\n"
                f"Last source message: {archive.get('last_source_message_id', 0)}"
            )
        else:
            await app.notify("No archive configured. Use /archive <chat>.")
    elif command == "/archive-stop":
        app.state.data.pop("archive", None)
        app.state.save()
        await app.notify("Live archive mirroring stopped.")
