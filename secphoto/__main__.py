# https://github.com/Dr-Muh/SecPhoto
import asyncio
from argparse import ArgumentParser
from zoneinfo import ZoneInfo

try:
    import socks  # noqa: F401
    import telethon  # noqa: F401
except ImportError:
    print(' [!] Please install dependencies~> python3 -m pip install -r requirements.txt')
    exit(0)

from . import config, handlers
from .app import App
from .archive import discover_archive_state
from .client import authenticate_user, connect, create_client
from .commands import get_command_channel
from .state import State


async def main():
    try:
        timezone = ZoneInfo(config.timezone_name)
    except Exception as e:
        print(f"Invalid TG_TIMEZONE value '{config.timezone_name}': {str(e)}")
        exit(0)

    parser = ArgumentParser(add_help=False)
    parser.add_argument('-p', '--proxy')
    parser.add_argument('-help', '--help', action='store_true')
    argv = parser.parse_args()

    if argv.help:
        print("Saves Telegram self-destructing photos and videos.")
        print("-p or --proxy IP:PORT sets a SOCKS5 proxy.")
        print("Example: -p 127.0.0.1:9050")
        print("TG_EXCLUDED_USERS can hold comma-separated usernames or user IDs to skip.")
        print("The tool monitors chats for self-destructing media and saves it.")
        print("It also checks replied messages and supports grouped media.")
        exit(0)

    print('Starting to monitor all chats for self-destructive media...')

    client = await connect(create_client(argv.proxy))

    if not await authenticate_user(client):
        print('Authentication failed. Exiting...')
        await client.disconnect()
        return

    state = State(config.archive_state_path)
    command_channel = await get_command_channel(client, state)
    app = App(client, state, timezone, command_channel)
    await discover_archive_state(client, state)

    handlers.register(app)
    await client.run_until_disconnected()


if '__main__' == __name__:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Bye :)')
