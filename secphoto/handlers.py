"""Telegram event handlers that route updates to the feature modules."""
from telethon import events
from telethon.tl.types import User

from . import config
from .archive import mirror_message, record_deletions
from .commands import handle_command
from .media import MediaSaver


def register(app):
    client = app.client
    media_saver = MediaSaver(app)

    @client.on(events.NewMessage)
    async def handler(event):
        if event.chat_id == app.command_channel_id:
            await handle_command(app, event)
            return

        try:
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', getattr(chat, 'first_name', 'Unknown'))
            username = getattr(chat, 'username', None)
        except Exception as e:
            print(f'Could not get chat info: {str(e)}')
            return

        if config.is_excluded_user(event.chat_id, username):
            print(f'Skipping excluded user or chat: {chat_title}')
            return

        await mirror_message(app, event.chat_id, chat, event.message)

        # Handle current message (single or album)
        if event.message.media:
            await media_saver.handle_message(event.message, chat_title, event.chat_id, username, is_reply=False)

        # Handle replied-to message if present
        if event.message.reply_to_msg_id:
            try:
                replied_message = await event.get_reply_message()
                if replied_message and replied_message.media:
                    await media_saver.handle_message(replied_message, chat_title, event.chat_id, username, is_reply=True)
            except Exception as e:
                print(f'Failed to process replied message: {str(e)}')

    @client.on(events.MessageDeleted)
    async def deleted_handler(event):
        """Notify Saved Messages when Telegram reports deleted messages."""
        if event.chat_id is None:
            return

        try:
            chat = await event.get_chat()
            chat_title = getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(event.chat_id)
        except Exception:
            chat = None
            chat_title = str(event.chat_id)

        if isinstance(chat, User):
            deleted_count = len(event.deleted_ids)
            await client.send_message(
                "me",
                f"{deleted_count} message{'s' if deleted_count != 1 else ''} deleted in {chat_title}. "
                "Telegram did not provide the deleting user's identity.",
            )
            print(f"Notified Saved Messages about {deleted_count} deleted message(s) in {chat_title}")

        await record_deletions(app, event.chat_id, event.deleted_ids)
