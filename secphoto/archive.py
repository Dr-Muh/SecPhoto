"""Copying a source chat into a private archive channel and mirroring new messages."""
import os

from telethon.errors import FloodWaitError
from telethon.utils import get_peer_id

from . import config
from .chats import create_private_channel, resolve_chat

ARCHIVE_TITLE_PREFIX = "SecPhoto Archive - "
METADATA_PREFIX = "[SecPhoto metadata] source_id="


async def discover_archive_state(client, state):
    """Recover state from a metadata message in an existing archive channel."""
    if state.archive:
        return
    async for dialog in client.iter_dialogs():
        channel = dialog.entity
        title = getattr(channel, "title", "")
        if not getattr(channel, "broadcast", False) or not title.startswith(ARCHIVE_TITLE_PREFIX):
            continue
        async for message in client.iter_messages(channel, limit=20):
            marker = message.raw_text or ""
            if marker.startswith(METADATA_PREFIX):
                source_id = marker.split("source_id=", 1)[1].split(" ", 1)[0]
                state.data["archive"] = {
                    "source_id": int(source_id),
                    "archive_id": get_peer_id(channel),
                    "source": marker.split(" source=", 1)[-1],
                }
                state.save()
                print(f"Recovered archive state from {title}")
                return


async def copy_message_to_archive(client, message, source, archive_channel):
    """Copy one message, falling back when forwarding is restricted."""
    try:
        copied = await client.forward_messages(
            archive_channel, message, from_peer=source
        )
        return copied[0] if isinstance(copied, list) else copied
    except FloodWaitError:
        raise
    except Exception:
        config.archive_tmp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = await client.download_media(message, str(config.archive_tmp_dir)) if message.media else None
        try:
            if temp_path:
                return await client.send_file(
                    archive_channel, temp_path, caption=message.message or ""
                )
            if message.message:
                return await client.send_message(archive_channel, message.message)
            return await client.send_message(archive_channel, "[Message without text]")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)


async def backfill_archive(app, source, archive_channel):
    """Copy messages newer than the saved position. Returns (count, paused_by_flood_wait)."""
    state = app.state
    count = 0
    last_message_id = state.archive.get("last_source_message_id", 0)
    async for message in app.client.iter_messages(source, reverse=True):
        if message.id <= last_message_id:
            continue
        try:
            await copy_message_to_archive(app.client, message, source, archive_channel)
        except FloodWaitError as e:
            state.save()
            print(
                f"Telegram flood wait: pause for {e.seconds} seconds. "
                "Archive progress was saved; run the archive command again later."
            )
            return count, True
        state.data["archive"]["last_source_message_id"] = message.id
        state.save()
        count += 1
        if count % 100 == 0:
            print(f"Archived {count} messages...")
    return count, False


async def create_or_sync_archive(app, chat_spec):
    client = app.client
    state = app.state
    async with state.lock:
        source = await resolve_chat(client, chat_spec)
        source_id = get_peer_id(source)
        existing = state.archive
        if existing and existing.get("source_id") == source_id:
            archive_channel = await client.get_entity(int(existing["archive_id"]))
            await app.notify(f"Syncing existing archive for {chat_spec}...")
        else:
            title = getattr(source, "title", None) or getattr(source, "first_name", None) or str(chat_spec)
            archive_channel = await create_private_channel(
                client,
                f"{ARCHIVE_TITLE_PREFIX}{title}"[:128],
                f"Private copy of {title} created by SecPhoto.",
            )
            state.data["archive"] = {
                "source_id": source_id,
                "archive_id": get_peer_id(archive_channel),
                "source": str(chat_spec),
                "last_source_message_id": 0,
            }
            state.save()
            await client.send_message(
                archive_channel,
                f"{METADATA_PREFIX}{source_id} source={chat_spec}",
            )

        count, paused = await backfill_archive(app, source, archive_channel)
        if paused:
            print(f"Archive paused after copying {count} messages. Run /archive {chat_spec} later to resume.")
            return
        await app.notify(
            f"Archive ready for {chat_spec}. Copied {count} new messages. "
            "New messages will be mirrored automatically."
        )


async def adopt_archive(app, archive_spec, source_spec):
    """Use an existing channel as the archive and mirror only messages from now on."""
    client = app.client
    source = await resolve_chat(client, source_spec)
    archive_channel = await resolve_chat(client, archive_spec)
    latest_source = await client.get_messages(source, limit=1)
    app.state.data["archive"] = {
        "source_id": get_peer_id(source),
        "archive_id": get_peer_id(archive_channel),
        "source": str(source_spec),
        "last_source_message_id": latest_source[0].id if latest_source else 0,
    }
    app.state.save()


async def mirror_message(app, chat_id, chat, message):
    """Copy a new message to the archive if it comes from the archived chat."""
    archive = app.state.archive
    if not archive or chat_id != archive["source_id"]:
        return
    try:
        archive_channel = await app.client.get_entity(int(archive["archive_id"]))
        await copy_message_to_archive(app.client, message, chat, archive_channel)
    except Exception as e:
        print(f"Failed to mirror message {message.id}: {str(e)}")


async def record_deletions(app, chat_id, deleted_ids):
    """Note deleted source messages in the archive; the copies are kept."""
    archive = app.state.archive
    if not archive or chat_id != archive["source_id"]:
        return
    try:
        archive_channel = await app.client.get_entity(int(archive["archive_id"]))
        for message_id in deleted_ids:
            await app.client.send_message(
                archive_channel,
                f"Source message {message_id} was deleted. The archived copy is retained.",
            )
    except Exception as e:
        print(f"Failed to record deleted archive messages: {str(e)}")
