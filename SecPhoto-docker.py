# t.me/Mr3rf1
# https://github.com/Dr-Muh/SecPhoto

import os

api_id = int(os.environ["TG_API_ID"])
api_hash = os.environ["TG_API_HASH"]
excluded_users_raw = os.environ.get("TG_EXCLUDED_USERS", "")
excluded_users = {
    entry.strip().lower()
    for entry in excluded_users_raw.split(",")
    if entry.strip()
}
timezone_name = os.environ.get("TZ", "Europe/Berlin")

async def main():
    try:
        from telethon import TelegramClient, events
        from telethon.errors import SessionPasswordNeededError
        from socks import SOCKS5
        from argparse import ArgumentParser
        import os
        import getpass
        import re
        import asyncio
        from datetime import datetime
        from zoneinfo import ZoneInfo
        import sqlite3
    except ImportError:
        print(' [!] Please install dependencies~> python3 -m pip install -r requirements.txt')
        exit(0)

    try:
        app_timezone = ZoneInfo(timezone_name)
    except Exception as e:
        print(f"Invalid TG_TIMEZONE value '{timezone_name}': {str(e)}")
        exit(0)

    # Album buffer: grouped_id -> list of messages, keyed per chat
    # Structure: { (chat_id, grouped_id): [msg, ...] }
    album_buffer = {}
    album_tasks = {}

    def get_phone_number():
        """Get phone number with validation for international format"""
        while True:
            phone = input("Enter your phone number with country code, e.g., +1234567890: ").strip()
            if re.match(r'^\+[1-9]\d{1,14}$', phone):
                return phone
            else:
                print("Invalid phone number format. Please use international format, for example +1234567890.")

    async def authenticate_user(client):
        """Authenticate user with proper checking and interactive input"""
        try:
            me = await client.get_me()
            if me:
                print(f"Already authenticated as: {me.first_name}")
                return True
        except Exception:
            pass

        print("Authentication required...")
        phone_number = get_phone_number()

        try:
            sent_code_request = await client.send_code_request(phone=phone_number)
            code = input("Enter your verification code: ")
            try:
                await client.sign_in(
                    phone=phone_number,
                    code=code,
                    phone_code_hash=sent_code_request.phone_code_hash,
                )
                print("Successfully authenticated!")
                return True
            except SessionPasswordNeededError:
                password = getpass.getpass("Enter your 2FA password: ")
                await client.sign_in(password=password)
                print("Successfully authenticated with 2FA!")
                return True
        except Exception as e:
            print(f"Authentication failed: {str(e)}")
            return False

    parser = ArgumentParser(add_help=False)
    parser.add_argument('-p', '--proxy')
    parser.add_argument('-help', '--help', action='store_true')
    argv = parser.parse_args()

    if argv.proxy is not None:
        ip = argv.proxy.split(':')[0]
        port = int(argv.proxy.split(':')[1])
        client = TelegramClient('/app/data/session', api_id, api_hash, proxy=(SOCKS5, ip, port))
    else:
        client = TelegramClient('/app/data/session', api_id, api_hash)

    if argv.help:
        print("Saves Telegram self-destructing photos and videos.")
        print("-p or --proxy IP:PORT sets a SOCKS5 proxy.")
        print("Example: -p 127.0.0.1:9050")
        print("TG_EXCLUDED_USERS can hold comma-separated usernames or user IDs to skip.")
        print("The tool monitors chats for self-destructing media and saves it.")
        print("It also checks replied messages and supports grouped media.")
        exit(0)

    print('Starting to monitor all chats for self-destructive media...')

    # Connect to Telegram with database lock fix
    try:
        await client.connect()
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            print("[!] Session database is locked. Deleting and creating a new one...")
            session_file = f"{client.session.filename}.session"
            journal_file = f"{client.session.filename}.session-journal"
            for f in [session_file, journal_file]:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                        print(f"Deleted: {f}")
                    except Exception as err:
                        print(f"Could not delete {f}: {err}")
            client = TelegramClient(client.session.filename, api_id, api_hash)
            await client.connect()
        else:
            raise

    if not await authenticate_user(client):
        print('Authentication failed. Exiting...')
        await client.disconnect()
        return

    def build_filename(username, chat_id, timestamp, index=None):
        """Build a filename stem as USERNAME(or id)_TIMESTAMP[_index]"""
        name = username if username else str(chat_id)
        # Sanitize for filesystem
        name = re.sub(r'[\\/:*?"<>|]', '_', name)
        stem = f"{name}_{timestamp}"
        if index is not None:
            stem = f"{stem}_{index}"
        return stem

    def is_excluded_user(chat_id, username):
        """Return True when the chat user matches TG_EXCLUDED_USERS."""
        if username and username.lower() in excluded_users:
            return True

        chat_id_text = str(chat_id)
        return chat_id_text in excluded_users or f"@{chat_id_text}" in excluded_users

    def build_caption(message, chat_id, username, is_reply=False, is_album=False):
        """Build the formatted caption for a saved media message"""
        lines = []
        if is_reply:
            lines.append("Replied Message")

        lines.append(f'Chat ID: <a href="tg://user?id={chat_id}">{chat_id}</a>')
        if is_album:
            lines.append('Album: YES')
        lines.append(f"Username: {'@' + username if username else 'None'}")
        lines.append(f"Message ID: {message.id}")
        lines.append(f"Date Time: {datetime.now(app_timezone).strftime('%Y/%m/%d %H:%M:%S')}")
        return '\n'.join(lines) + '\n'

    async def process_album(messages, chat_title, chat_id, username, is_reply=False):
        """Download and forward an album (grouped media) as a single album"""
        try:
            file_paths = []
            for msg in messages:
                if not msg.media:
                    continue
                ext = 'jpg' if hasattr(msg.media, 'photo') and msg.media.photo else 'media'
                ts = datetime.now(app_timezone).strftime('%Y%m%d_%H%M%S')
                stem = build_filename(username, chat_id, ts, index=len(file_paths))
                path = await client.download_media(msg.media, f'{stem}.{ext}')
                if path:
                    file_paths.append(path)

            if not file_paths:
                return

            caption = build_caption(messages[0], chat_id, username, is_reply=is_reply, is_album=True)
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

    async def process_single_media(message, chat_title, chat_id, username, is_reply=False):
        """Process a single self-destructive media message"""
        try:
            caption = build_caption(message, chat_id, username, is_reply=is_reply, is_album=False)
            label = chat_title + (' (replied message)' if is_reply else '')

            ts = datetime.now(app_timezone).strftime('%Y%m%d_%H%M%S')
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

    def is_self_destructive(message):
        """Return True if the message contains self-destructive (ttl) media"""
        return (
            message.media is not None
            and hasattr(message.media, 'ttl_seconds')
            and message.media.ttl_seconds
        )

    async def flush_album(key, chat_title, chat_id, username, is_reply=False):
        """Wait briefly to collect all album parts, then process them together"""
        await asyncio.sleep(0.6)  # short debounce to gather all grouped messages
        messages = album_buffer.pop(key, [])
        album_tasks.pop(key, None)
        if messages:
            # Sort by message id to preserve order
            messages.sort(key=lambda m: m.id)
            await process_album(messages, chat_title, chat_id, username, is_reply=is_reply)

    async def handle_message(message, chat_title, chat_id, username, is_reply=False):
        """Route a message to single or album processing based on grouped_id"""
        if not is_self_destructive(message):
            return

        grouped_id = getattr(message, 'grouped_id', None)

        if grouped_id:
            key = (chat_id, grouped_id)
            if key not in album_buffer:
                album_buffer[key] = []
            album_buffer[key].append(message)

            # Cancel existing flush task and restart debounce timer
            if key in album_tasks and not album_tasks[key].done():
                album_tasks[key].cancel()
            album_tasks[key] = asyncio.ensure_future(
                flush_album(key, chat_title, chat_id, username, is_reply=is_reply)
            )
        else:
            await process_single_media(message, chat_title, chat_id, username, is_reply=is_reply)

    @client.on(events.NewMessage)
    async def handler(event):
        try:
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', getattr(chat, 'first_name', 'Unknown'))
            username = getattr(chat, 'username', None)
        except Exception as e:
            print(f'Could not get chat info: {str(e)}')
            return

        if is_excluded_user(event.chat_id, username):
            print(f'Skipping excluded user or chat: {chat_title}')
            return

        # Handle current message (single or album)
        if event.message.media:
            await handle_message(event.message, chat_title, event.chat_id, username, is_reply=False)

        # Handle replied-to message if present
        if event.message.reply_to_msg_id:
            try:
                replied_message = await event.get_reply_message()
                if replied_message and replied_message.media:
                    await handle_message(replied_message, chat_title, event.chat_id, username, is_reply=True)
            except Exception as e:
                print(f'Failed to process replied message: {str(e)}')

    await client.run_until_disconnected()

if '__main__' == __name__:
    try:
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Bye :)')
