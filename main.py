import asyncio
import os
from aiohttp import web
from dotenv import load_dotenv
from botbuilder.core import BotFrameworkAdapterSettings, BotFrameworkAdapter, TurnContext
from botbuilder.schema import Activity
import requests
import traceback
import sys

# Load .env variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Adapter with error handling
class AdapterWithErrorHandler(BotFrameworkAdapter):
    async def on_error(self, context: TurnContext, error: Exception):
        print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
        traceback.print_exc()
        
        # Send error message to user
        if context:
            await context.send_activity("The bot encountered an error. Please try again.")

# Adapter settings with proper error handling
APP_ID = os.getenv("MicrosoftAppId", "88d2a123-d987-426e-b7f1-b4c82678b65a")  
APP_PASSWORD = os.getenv("MicrosoftAppPassword", "")
adapter_settings = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
adapter = AdapterWithErrorHandler(adapter_settings)

# HR-specific system prompt
HR_SYSTEM_PROMPT = """
You are an HR assistant for a company. You help employees understand HR policies such as leave, benefits, remote work, dress code, and performance reviews.
"""

# Main bot logic
async def on_message_activity(turn_context: TurnContext):
    try:
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
        
        print(f"Sending request to Groq with message: {user_message}")
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data
        )
        
        print(f"Groq API response status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            reply = f"Sorry, I couldn't process your question. Please try again later."
        else:
            result = response.json()
            reply = result["choices"][0]["message"]["content"]
        
        await turn_context.send_activity(reply.strip())
        
    except Exception as e:
        print(f"Error in message activity: {str(e)}")
        traceback.print_exc()
        await turn_context.send_activity("Sorry, I encountered an error processing your request.")

# Health check endpoint
async def health_check(req: web.Request):
    return web.json_response({"status": "ok", "message": "Bot is running"})

# Request handler for messages
async def messages(req: web.Request):
    try:
        print("Received message request")
        body = await req.json()
        print(f"Request body: {body}")
        
        activity = Activity().deserialize(body)
        
        # Add service_url if it's missing (for testing purposes)
        if not activity.service_url:
            activity.service_url = "https://smba.trafficmanager.net/teams/"
        
        async def aux_func(turn_context):
            await on_message_activity(turn_context)
        
        await adapter.process_activity(activity, "", aux_func)
        return web.Response(status=200)
    except Exception as e:
        print(f"Error in messages handler: {str(e)}")
        traceback.print_exc()
        return web.Response(status=500, text=f"Internal server error: {str(e)}")

# Set up server
app = web.Application()
app.router.add_post("/api/messages", messages)  # Bot messages endpoint
app.router.add_get("/health", health_check)    # Health check endpoint

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 8000))
        print(f"Starting bot on port {port}")
        web.run_app(app, host="0.0.0.0", port=port)
    except Exception as e:
        print(f"Error starting the app: {str(e)}")
        traceback.print_exc()
