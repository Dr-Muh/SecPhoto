# SecPhoto

A Telegram userbot that runs on your own account. It saves self-destructing photos and videos, mirrors chats into private archive channels, and exports chat history to Markdown. You control it with commands in a private Telegram channel.

Forked from [Mr3rf1/SecPhoto](https://github.com/Mr3rf1/SecPhoto).

## Features

- **Self-destructing media:** photos and videos with a timer are saved to your Saved Messages as soon as they arrive. Albums are kept together. If you missed one, reply to it and it is saved.
- **Chat archive:** copies a chat or channel into a private archive channel, then mirrors new messages as they arrive. Deleted source messages stay in the archive.
- **Deletion alerts:** when messages are deleted in a private chat, you get a notice in Saved Messages with the chat and the number of messages.
- **Markdown export:** sends the latest messages of a chat as a `.md` file.
- **Chat lookup:** lists the IDs of your chats, groups and channels, optionally filtered by name.

## Requirements

- Docker with Docker Compose (or Portainer)
- A Telegram account
- Your own Telegram API credentials

### Getting API credentials

1. Log in at [my.telegram.org](https://my.telegram.org) with your phone number.
2. Open **API Development Tools** and create an application. Any title and short name will do; choose **Desktop** as the platform.
3. Note the **api_id** (a number) and **api_hash** (32 characters). Keep both private.

## Setup

1. Clone the repository and build the image:

   ```bash
   git clone https://github.com/Dr-Muh/SecPhoto
   cd SecPhoto
   docker build -t secphoto .
   ```

   To build on one machine and run on another (for example a linux/amd64 server):

   ```bash
   docker build --platform linux/amd64 -t secphoto .
   docker save -o secphoto.tar secphoto
   # on the target machine
   docker load -i secphoto.tar
   ```

2. Create a `.env` file next to `docker-compose.yml`:

   ```env
   TG_API_ID=1234567
   TG_API_HASH=your_api_hash
   TG_EXCLUDED_USERS=
   TG_COMMAND_CHANNEL_ID=
   ```

   In Portainer, create a stack from `docker-compose.yml` and set these as environment variables instead.

3. Start the container and attach to it to log in:

   ```bash
   docker compose up -d
   docker attach telegram-secphoto
   ```

   On the first start you are asked for your phone number, the login code and, if enabled, your 2FA password. Once you're logged in, detach with `Ctrl+P` then `Ctrl+Q` and the container keeps running. If you started the container in the background without attaching, use `docker start -ai telegram-secphoto` to get the prompt.

The login session and the bot's settings are stored in `./data`, so restarts and rebuilds keep you logged in. Keep that folder private: anyone with the session file can access your Telegram account.

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TG_API_ID` | yes | API ID from my.telegram.org |
| `TG_API_HASH` | yes | API hash from my.telegram.org |
| `TG_EXCLUDED_USERS` | no | Comma-separated usernames or chat IDs to ignore entirely (no media saving, no mirroring) |
| `TG_COMMAND_CHANNEL_ID` | no | Use an existing channel for commands instead of creating one |
| `TG_ARCHIVE_STATE_PATH` | no | Where the bot's settings are stored; defaults to `/app/data/archive_state.json` |
| `TZ` | no | Time zone for timestamps; defaults to `Europe/Berlin` |

## Commands

On first start the bot creates a private channel called **SecPhoto Commands**. Send commands there:

```text
/help
/chats [name filter]
/export <chat> [limit]
/archive <chat> [--copy]
/archive-adopt <archive-channel-id> <source-chat>
/archive-status
/archive-stop
```

`<chat>` can be a `@username`, an invite link, a numeric chat ID or the exact name of a chat.

| Command | Description |
|---------|-------------|
| `/help` | Lists all commands. |
| `/chats [filter]` | Lists the ID, type and name of every chat, group and channel. Text after the command shows only chats whose name contains it, e.g. `/chats news`. |
| `/export <chat> [limit]` | Sends the latest messages of a chat as a Markdown file, with sender, time, replies and media types. The default limit is 200. |
| `/archive <chat> [--copy]` | Creates a private archive channel, copies the chat's existing messages in order, then mirrors new ones. Running it again for the same chat resumes where it stopped. |
| `/archive-adopt <archive> <source>` | Uses an existing channel as the archive for a source chat. Existing messages are left as they are; only new source messages are mirrored. |
| `/archive-status` | Shows the source, archive channel, mode and progress. |
| `/archive-stop` | Stops mirroring. The archive channel is kept. |

### Archive details

- **Forward or copy:** messages are forwarded by default, so they show a "Forwarded from" header. With `--copy` they are posted as new messages, keeping text, formatting and media, for a copy of a channel without forward headers. The mode is remembered for the archive.
- **Protected chats:** if a chat doesn't allow forwarding or saving, the media is downloaded and uploaded again where Telegram allows it. Some service messages and restricted media can't be copied.
- **Not identical:** archived messages carry the date they were posted to the archive, and albums arrive as separate posts. The archive also gets a metadata message at the top and a notice for each deleted source message.
- **Rate limits:** when Telegram rate-limits a large backfill, progress is saved. Run the same `/archive` command later to continue.
- **One at a time:** only one archive is mirrored at a time. Starting an archive for another chat replaces the current one.

## Running without Docker

The bot expects its data folder at `/app/data`, so Docker is the easiest way to run it. To run it directly, create that folder, install the dependencies and set the environment variables:

```bash
python3 -m pip install -r requirements.txt
export TG_API_ID=1234567 TG_API_HASH=your_api_hash
python3 -m secphoto
```

Add `-p IP:PORT` to connect through a SOCKS5 proxy such as Tor, e.g. `python3 -m secphoto -p 127.0.0.1:9050`.

## Troubleshooting

- **Login fails or the session is broken:** stop the container, delete `data/session.session` and start again to log in from scratch.
- **"Session database is locked":** the bot deletes the locked session and asks you to log in again.
- **A command does nothing:** make sure you sent it in the SecPhoto Commands channel. Send `/help` to check that the bot responds.

## Disclaimer

This project is for educational purposes. Respect Telegram's Terms of Service and the privacy of the people you chat with.
