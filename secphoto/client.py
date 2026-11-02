"""Telegram client creation, connection and interactive login."""
import getpass
import os
import re
import sqlite3

from socks import SOCKS5
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from . import config


def create_client(proxy=None):
    """Create a client, optionally routed through a SOCKS5 proxy given as IP:PORT."""
    if proxy is not None:
        ip = proxy.split(':')[0]
        port = int(proxy.split(':')[1])
        return TelegramClient(config.session_path, config.api_id, config.api_hash, proxy=(SOCKS5, ip, port))
    return TelegramClient(config.session_path, config.api_id, config.api_hash)


async def connect(client):
    """Connect and return the client, recreating the session if its database is locked."""
    try:
        await client.connect()
        return client
    except sqlite3.OperationalError as e:
        if "database is locked" not in str(e).lower():
            raise
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
        client = TelegramClient(client.session.filename, config.api_id, config.api_hash)
        await client.connect()
        return client


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
