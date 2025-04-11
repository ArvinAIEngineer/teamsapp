import asyncio
import os
from aiohttp import web
from dotenv import load_dotenv
from botbuilder.core import BotFrameworkAdapterSettings, BotFrameworkAdapter, TurnContext
from botbuilder.schema import Activity
import requests

# Load .env variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Adapter in unauthenticated mode
adapter_settings = BotFrameworkAdapterSettings("", "")
adapter = BotFrameworkAdapter(adapter_settings)

# HR-specific system prompt
HR_SYSTEM_PROMPT = """
You are an HR assistant for a company. You help employees understand HR policies such as leave, benefits, remote work, dress code, and performance reviews.
"""

# Main bot logic
async def on_message_activity(turn_context: TurnContext):
    user_message = turn_context.activity.text.strip()
    
    if not user_message:
        await turn_context.send_activity("Please enter a valid HR question.")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }

    data = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "messages": [
            {"role": "system", "content": HR_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=data
    )

    if response.status_code != 200:
        reply = f"Error from Groq API: {response.status_code} - {response.text}"
    else:
        result = response.json()
        reply = result["choices"][0]["message"]["content"]

    await turn_context.send_activity(reply.strip())

# Health check endpoint
async def health_check(req: web.Request):
    return web.json_response({"status": "ok", "message": "Bot is running"})

# Request handler for messages
async def messages(req: web.Request):
    body = await req.json()
    activity = Activity().deserialize(body)

    async def aux_func(turn_context):
        await on_message_activity(turn_context)

    await adapter.process_activity(activity, "", aux_func)
    return web.Response(status=200)

# Set up server
app = web.Application()
app.router.add_post("/api/messages", messages)  # Bot messages endpoint
app.router.add_get("/health", health_check)    # Health check endpoint

if __name__ == "__main__":
    try:
        # Run app on port 8000 as required by Render
        web.run_app(app, host="0.0.0.0", port=8000)
    except Exception as e:
        raise e
