"""
Run this script ONCE locally to authenticate with Telegram and get your session string.
The printed string is stored as TELEGRAM_SESSION in your Netlify environment variables.

Usage:
    pip install telethon python-dotenv
    python setup_auth.py
"""

import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID   = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
PHONE    = os.environ.get("TELEGRAM_PHONE", "")


async def main():
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        phone = PHONE or input("Phone number (with country code, e.g. +61...): ").strip()
        await client.send_code_request(phone)
        code = input("Enter the code Telegram just sent you: ").strip()
        try:
            await client.sign_in(phone, code)
        except Exception:
            password = input("2FA password: ").strip()
            await client.sign_in(password=password)

        session_string = client.session.save()
        print("\n" + "=" * 60)
        print("SUCCESS! Copy the line below into Netlify as TELEGRAM_SESSION:")
        print("=" * 60)
        print(session_string)
        print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
