"""Shared objects passed to every feature module."""
from telethon.errors import FloodWaitError
from telethon.utils import get_peer_id

# Telegram caps messages at 4096 characters
MESSAGE_LIMIT = 4000


class App:
    def __init__(self, client, state, timezone, command_channel):
        self.client = client
        self.state = state
        self.timezone = timezone
        self.command_channel = command_channel
        self.command_channel_id = get_peer_id(command_channel)

    async def notify(self, text):
        """Send a message to the command channel without raising."""
        try:
            await self.client.send_message(self.command_channel, text)
        except FloodWaitError as e:
            print(f"Could not notify command channel; flood wait is {e.seconds} seconds")
        except Exception as e:
            print(f"Could not notify command channel: {e}")

    async def notify_lines(self, header, lines):
        """Send a header and lines, split into as few messages as the size limit allows."""
        chunk = header
        for line in lines:
            if len(chunk) + len(line) + 1 > MESSAGE_LIMIT:
                await self.notify(chunk)
                chunk = line
            else:
                chunk += "\n" + line
        await self.notify(chunk)

    async def report_error(self, message):
        print(f"Command failed: {message}")
        await self.notify(message)
