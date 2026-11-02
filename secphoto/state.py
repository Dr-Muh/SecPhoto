"""Persistent archive and command channel settings stored as JSON."""
import asyncio
import json


class State:
    def __init__(self, path):
        self.path = path
        self.data = self._load()
        self.lock = asyncio.Lock()

    def _load(self):
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"Could not read archive state: {str(e)}")
            return {}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=True, indent=2), encoding="utf-8"
        )

    @property
    def archive(self):
        return self.data.get("archive")
