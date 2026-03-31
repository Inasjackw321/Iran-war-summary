import os
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
_model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")


def summarize(channel_name: str, messages: list[str]) -> str:
    if not messages:
        return "No messages in the last 24 hours."

    prompt = f"""You are a news analyst. Below are messages from the Telegram channel "{channel_name}", collected over the last 24 hours.

Write a concise summary in English (under 300 words) covering:
- Main topics and events discussed
- Key facts, numbers, or names mentioned
- Overall tone of the channel

Use bullet points where helpful.

--- MESSAGES ---
{chr(10).join(messages[:500])}
--- END ---"""

    return _model.generate_content(prompt).text
