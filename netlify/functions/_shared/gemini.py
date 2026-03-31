import os
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
_model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")


def summarize(channel_name: str, messages: list[str]) -> str:
    if not messages:
        return "No messages in the last 24 hours."

    combined = "\n\n".join(messages[:500])
    prompt = f"""You are a news analyst. Below are messages from a Telegram channel called "{channel_name}" collected over the last 24 hours.

Write a clear, concise summary in English covering:
- The main topics and events discussed
- Key facts, numbers, or names mentioned
- Overall tone or sentiment of the channel

Keep it under 300 words. Use bullet points where helpful.

--- MESSAGES START ---
{combined}
--- MESSAGES END ---"""

    response = _model.generate_content(prompt)
    return response.text
