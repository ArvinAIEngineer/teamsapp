import asyncio
import os
from aiohttp import web
from dotenv import load_dotenv
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    BotFrameworkAdapter,
    TurnContext,
)
from botbuilder.schema import Activity
import requests
import traceback
import sys

# Load environment variables
load_dotenv()

# DEBUG: Check environment values
MICROSOFT_APP_ID = os.getenv("MicrosoftAppId")
MICROSOFT_APP_PASSWORD = os.getenv("MicrosoftAppPassword")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

print(f"[DEBUG] MICROSOFT_APP_ID = {MICROSOFT_APP_ID}", flush=True)
print(f"[DEBUG] MICROSOFT_APP_PASSWORD = {'SET' if MICROSOFT_APP_PASSWORD else 'NOT SET'}", flush=True)
print(f"[DEBUG] GROQ_API_KEY = {'SET' if GROQ_API_KEY else 'NOT SET'}", flush=True)

# Adapter with error handling
class AdapterWithErrorHandler(BotFrameworkAdapter):
    async def on_error(self, context: TurnContext, error: Exception):
        print(f"\n[on_turn_error] unhandled error: {error}", file=sys.stderr, flush=True)
        traceback.print_exc()
        if context:
            await context.send_activity("The bot encountered an error. Please try again.")

# Initialize adapter (auth enabled)
adapter_settings = BotFrameworkAdapterSettings(MICROSOFT_APP_ID, MICROSOFT_APP_PASSWORD)

# OPTIONAL: Disable auth for debugging only
# adapter_settings = BotFrameworkAdapterSettings("", "")

adapter = AdapterWithErrorHandler(adapter_settings)

# HR-specific system prompt
HR_SYSTEM_PROMPT = """
You are an HR assistant for a company. You help employees with:
- Leave policies (vacation, sick leave)
- Benefits (health insurance, 401k)
- Remote work policies
- Dress code
- Performance reviews
Respond concisely and professionally.
"""

# Bot logic
async def on_message_activity(turn_context: TurnContext):
    try:
        user_message = turn_context.activity.text.strip()
        
        if not user_message:
            await turn_context.send_activity("Please ask an HR-related question.")
            return
        
        print("[DEBUG] User message received:", user_message, flush=True)
        
        # Call Groq API
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": HR_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
        }
        
        print("[DEBUG] Sending request to Groq API...", flush=True)
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10,
        )
        
        print(f"[DEBUG] Groq API response: {response.status_code} - {response.text}", flush=True)

        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
        else:
            reply = "Sorry, I couldn't process your HR question. Please try again later."

        await turn_context.send_activity(reply.strip())
        
    except Exception as e:
        print(f"[ERROR] Exception in bot logic: {str(e)}", flush=True)
        traceback.print_exc()
        await turn_context.send_activity("Sorry, I encountered an error.")

# HTTP endpoints
async def health_check(request: web.Request):
    return web.json_response({"status": "ok"})

async def messages(request: web.Request):
    if "application/json" not in request.headers["Content-Type"]:
        return web.Response(status=415)
    
    try:
        body = await request.json()
        activity = Activity().deserialize(body)
        auth_header = request.headers.get("Authorization", "")
        
        async def aux_func(turn_context):
            await on_message_activity(turn_context)
        
        print("[DEBUG] Processing incoming activity...", flush=True)
        await adapter.process_activity(activity, auth_header, aux_func)
        return web.Response(status=200)
    
    except Exception as e:
        print(f"[ERROR] Error in /api/messages: {str(e)}", flush=True)
        traceback.print_exc()
        return web.Response(status=500, text=str(e))

# Server setup
app = web.Application()
app.router.add_post("/api/messages", messages)
app.router.add_get("/health", health_check)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting server on port {port}", flush=True)
    web.run_app(app, host="0.0.0.0", port=port)
