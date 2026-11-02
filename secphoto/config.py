"""Settings read from environment variables."""
import os
from pathlib import Path

data_dir = Path("/app/data")
session_path = str(data_dir / "session")
archive_tmp_dir = data_dir / "archive_tmp"

api_id = int(os.environ["TG_API_ID"])
api_hash = os.environ["TG_API_HASH"]
excluded_users_raw = os.environ.get("TG_EXCLUDED_USERS", "")
excluded_users = {
    entry.strip().lower()
    for entry in excluded_users_raw.split(",")
    if entry.strip()
}
timezone_name = os.environ.get("TZ", "Europe/Berlin")
archive_state_path = Path(
    os.environ.get("TG_ARCHIVE_STATE_PATH", str(data_dir / "archive_state.json"))
)
command_channel_id = os.environ.get("TG_COMMAND_CHANNEL_ID")


def is_excluded_user(chat_id, username):
    """Return True when the chat user matches TG_EXCLUDED_USERS."""
    if username and username.lower() in excluded_users:
        return True

    chat_id_text = str(chat_id)
    return chat_id_text in excluded_users or f"@{chat_id_text}" in excluded_users
