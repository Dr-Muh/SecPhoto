"""Saving self-destructing photos and videos to Saved Messages."""
import asyncio
import os
import re
from datetime import datetime


def build_filename(username, chat_id, timestamp, index=None):
    """Build a filename stem as USERNAME(or id)_TIMESTAMP[_index]"""
    name = username if username else str(chat_id)
    # Sanitize for filesystem
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    stem = f"{name}_{timestamp}"
    if index is not None:
        stem = f"{stem}_{index}"
    return stem


def is_self_destructive(message):
    """Return True if the message contains self-destructive (ttl) media"""
    return (
        message.media is not None
        and hasattr(message.media, 'ttl_seconds')
        and message.media.ttl_seconds
    )


class MediaSaver:
    def __init__(self, app):
        self.app = app
        # Album buffer keyed per chat: { (chat_id, grouped_id): [msg, ...] }
        self.album_buffer = {}
        self.album_tasks = {}

    def build_caption(self, message, chat_id, username, is_reply=False, is_album=False):
        """Build the formatted caption for a saved media message"""
        lines = []
        if is_reply:
            lines.append("Replied Message")

        lines.append(f'Chat ID: <a href="tg://user?id={chat_id}">{chat_id}</a>')
        if is_album:
            lines.append('Album: YES')
        lines.append(f"Username: {'@' + username if username else 'None'}")
        lines.append(f"Message ID: {message.id}")
        lines.append(f"Date Time: {datetime.now(self.app.timezone).strftime('%Y/%m/%d %H:%M:%S')}")
        return '\n'.join(lines) + '\n'

    async def process_album(self, messages, chat_title, chat_id, username, is_reply=False):
        """Download and forward an album (grouped media) as a single album"""
        client = self.app.client
        try:
            file_paths = []
            for msg in messages:
                if not msg.media:
                    continue
                ext = 'jpg' if hasattr(msg.media, 'photo') and msg.media.photo else 'media'
                ts = datetime.now(self.app.timezone).strftime('%Y%m%d_%H%M%S')
                stem = build_filename(username, chat_id, ts, index=len(file_paths))
                path = await client.download_media(msg.media, f'{stem}.{ext}')
                if path:
                    file_paths.append(path)

            if not file_paths:
                return

            caption = self.build_caption(messages[0], chat_id, username, is_reply=is_reply, is_album=True)
            label = chat_title + (' (replied message)' if is_reply else '')
            print(f'Saving album ({len(file_paths)} items) from {label}...', end='')

            file_handles = [open(p, 'rb') for p in file_paths]
            try:
                await client.send_file('me', file_handles, caption=caption, parse_mode='html')
            finally:
                for fh in file_handles:
                    fh.close()

            print(f'\rAlbum ({len(file_paths)} items) from {label} saved to Saved Messages')

            for p in file_paths:
                try:
                    os.remove(p)
                except Exception:
                    pass
        except Exception as e:
            print(f'Failed to process album: {str(e)}')

    async def process_single_media(self, message, chat_title, chat_id, username, is_reply=False):
        """Process a single self-destructive media message"""
        client = self.app.client
        try:
            caption = self.build_caption(message, chat_id, username, is_reply=is_reply, is_album=False)
            label = chat_title + (' (replied message)' if is_reply else '')

            ts = datetime.now(self.app.timezone).strftime('%Y%m%d_%H%M%S')
            stem = build_filename(username, chat_id, ts)

            if hasattr(message.media, 'photo') and message.media.photo:
                print(f'Found self-destructing photo in {label}. Downloading...', end='')
                file_path = await client.download_media(message.media, f'{stem}.jpg')
                media_type = 'photo'
            elif hasattr(message.media, 'document') and message.media.document:
                print(f'Found self-destructing media in {label}. Downloading...', end='')
                file_path = await client.download_media(message.media, f'{stem}.media')
                media_type = 'media'
            else:
                return

            if file_path:
                with open(file_path, 'rb') as file:
                    await client.send_file('me', file, caption=caption, parse_mode='html')
                print(f'\rSaved {media_type} from {label} to Saved Messages')
                os.remove(file_path)
        except Exception as e:
            print(f'Failed to process self-destructive media: {str(e)}')

    async def flush_album(self, key, chat_title, chat_id, username, is_reply=False):
        """Wait briefly to collect all album parts, then process them together"""
        await asyncio.sleep(0.6)  # short debounce to gather all grouped messages
        messages = self.album_buffer.pop(key, [])
        self.album_tasks.pop(key, None)
        if messages:
            # Sort by message id to preserve order
            messages.sort(key=lambda m: m.id)
            await self.process_album(messages, chat_title, chat_id, username, is_reply=is_reply)

    async def handle_message(self, message, chat_title, chat_id, username, is_reply=False):
        """Route a message to single or album processing based on grouped_id"""
        if not is_self_destructive(message):
            return

        grouped_id = getattr(message, 'grouped_id', None)

        if grouped_id:
            key = (chat_id, grouped_id)
            if key not in self.album_buffer:
                self.album_buffer[key] = []
            self.album_buffer[key].append(message)

            # Cancel existing flush task and restart debounce timer
            if key in self.album_tasks and not self.album_tasks[key].done():
                self.album_tasks[key].cancel()
            self.album_tasks[key] = asyncio.ensure_future(
                self.flush_album(key, chat_title, chat_id, username, is_reply=is_reply)
            )
        else:
            await self.process_single_media(message, chat_title, chat_id, username, is_reply=is_reply)
