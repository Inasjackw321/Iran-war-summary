"""
Run this ONCE locally to get your Telegram session string.
Then save the output as the TELEGRAM_SESSION GitHub Secret.

Usage:
    pip install telethon
    python script/setup_auth.py
"""

import asyncio, os
from dotenv import load_dotenv
load_dotenv()
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID   = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
PHONE    = os.environ.get("TELEGRAM_PHONE", "")

async def main():
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        phone = PHONE or input("Phone (with country code, e.g. +61...): ").strip()
        await client.send_code_request(phone)
        code = input("Telegram verification code: ").strip()
        try:
            await client.sign_in(phone, code)
        except Exception:
            pw = input("2FA password: ").strip()
            await client.sign_in(password=pw)

        s = client.session.save()
        print("\n" + "="*60)
        print("Copy the line below → add as GitHub Secret TELEGRAM_SESSION")
        print("="*60)
        print(s)
        print("="*60)

asyncio.run(main())
