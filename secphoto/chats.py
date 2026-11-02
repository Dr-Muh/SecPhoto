"""Chat lookup and channel creation helpers."""
import re

from telethon.tl.functions.channels import CreateChannelRequest


async def create_private_channel(client, title, about):
    result = await client(CreateChannelRequest(
        title=title,
        about=about,
        broadcast=True,
        megagroup=False,
    ))
    return result.chats[0]


async def resolve_chat(client, chat_spec):
    """Resolve a username, link or numeric chat ID given as command text."""
    # Telethon parses numeric strings as phone numbers, so IDs must be ints
    if re.fullmatch(r"-?\d+", chat_spec):
        return await client.get_entity(int(chat_spec))
    return await client.get_entity(chat_spec)
