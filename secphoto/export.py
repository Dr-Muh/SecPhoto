"""Markdown transcripts of a chat's recent message history."""
import io
import re
from datetime import datetime

from telethon.tl.types import DocumentAttributeFilename
from telethon.utils import get_display_name, get_peer_id

from .chats import resolve_chat

DEFAULT_LIMIT = 200


def chat_kind(entity):
    if getattr(entity, "broadcast", False):
        return "channel"
    if getattr(entity, "megagroup", False) or getattr(entity, "title", None):
        return "group"
    return "user"


def sender_label(message, chat):
    """Display name plus @username; channel posts without a sender use the chat."""
    sender = message.sender or chat
    name = get_display_name(sender) or str(message.sender_id)
    username = getattr(sender, "username", None)
    return f"{name} (@{username})" if username else name


def media_label(message):
    # Order matters: a voice message is also audio, a GIF is also a video, etc.
    if message.photo:
        return "[photo]"
    if message.voice:
        return "[voice message]"
    if message.video_note:
        return "[video message]"
    if message.gif:
        return "[GIF]"
    if message.video:
        return "[video]"
    if message.sticker:
        return "[sticker]"
    if message.audio:
        return "[audio]"
    if message.poll:
        return "[poll]"
    if message.geo:
        return "[location]"
    if message.contact:
        return "[contact]"
    if message.document:
        name = message.file.name if message.file else None
        return f"[file: {name}]" if name else "[file]"
    if message.media:
        return "[media]"
    return None


def format_message(message, chat, timezone):
    """Format one message as a header line plus its text, or None if it has no content."""
    text = message.message or ""
    media = media_label(message)
    if not text and not media:
        return None

    header = f"**{sender_label(message, chat)}** · {message.date.astimezone(timezone):%Y-%m-%d %H:%M} · #{message.id}"
    if message.reply_to_msg_id:
        header += f" · reply to #{message.reply_to_msg_id}"
    if message.fwd_from:
        header += " · forwarded"

    body = "\n".join(part for part in (media, text) if part)
    return f"{header}\n{body}"


async def build_transcript(client, chat, limit, timezone):
    """Return (markdown, message_count) for the last `limit` messages, oldest first."""
    messages = [m async for m in client.iter_messages(chat, limit=limit)]
    messages.reverse()

    entries = [entry for entry in (format_message(m, chat, timezone) for m in messages) if entry]
    title = get_display_name(chat)

    lines = [
        f"# Chat history: {title}",
        "",
        f"- Chat: {title} ({chat_kind(chat)}, ID {get_peer_id(chat)})",
        f"- Messages: {len(entries)}",
    ]
    if messages:
        lines.append(
            f"- Period: {messages[0].date.astimezone(timezone):%Y-%m-%d %H:%M} "
            f"to {messages[-1].date.astimezone(timezone):%Y-%m-%d %H:%M}"
        )
    lines.append(f"- Exported: {datetime.now(timezone):%Y-%m-%d %H:%M}")
    lines += ["", "---", ""]
    lines.append("\n\n".join(entries))
    return "\n".join(lines) + "\n", len(entries)


async def export_chat(app, chat_spec, limit=DEFAULT_LIMIT):
    """Send the chat's last messages as a Markdown file to the command channel."""
    chat = await resolve_chat(app.client, chat_spec)
    markdown, count = await build_transcript(app.client, chat, limit, app.timezone)

    title = get_display_name(chat)
    safe_title = re.sub(r'[\\/:*?"<>|\s]+', '_', title).strip('_') or str(get_peer_id(chat))
    file_name = f"{safe_title}_{datetime.now(app.timezone):%Y%m%d_%H%M%S}.md"

    await app.client.send_file(
        app.command_channel,
        io.BytesIO(markdown.encode("utf-8")),
        caption=f"Last {count} messages from {title}",
        force_document=True,
        attributes=[DocumentAttributeFilename(file_name)],
    )
