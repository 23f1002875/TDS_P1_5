import os
import json
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from agent import DataAnalystAgent
from logger import RunLogger

# In-memory dictionary for conversational history
# Structure: user_id -> [{"role": "user"/"assistant", "content": "..."}]
user_memories = defaultdict(list)

# Single agent instance
agent = DataAnalystAgent()

async def start_command(update: Update, context: CallbackContext) -> None:
    """Handles the /start command."""
    user_id = update.effective_user.id
    user_memories[user_id] = []
    
    instructions = (
        "Hello! I am a Data Analyst Bot.\n"
        "Send me URLs to datasets (CSV, JSON, Excel, ZIP), inline tables, or plain questions.\n"
        "Include the EXACT JSON structure you want me to reply with in your message."
    )
    # The start message is the only markdown allowed, per strict adherence 
    # the "Final Telegram Reply" rule applies to queries.
    await update.message.reply_text(instructions)

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handles normal text messages."""
    user_id = update.effective_user.id
    user_text = update.message.text

    # 1. Update memory
    user_memories[user_id].append({"role": "user", "content": user_text})
    
    host_url = os.getenv("HOST_URL", os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000"))
    logger = RunLogger(host_url)

    try:
        # 2. Run agent
        final_response_dict = await agent.process_conversation(user_memories[user_id], logger)
        
        # 3. Add assistant reply to memory
        user_memories[user_id].append({"role": "assistant", "content": json.dumps(final_response_dict)})
        
        # 4. Reply STRICTLY with one JSON object and NOTHING ELSE. No markdown.
        exact_json_string = json.dumps(final_response_dict, separators=(',', ':'))
        await update.message.reply_text(text=exact_json_string)
        
    except Exception as e:
        # Fallback strict JSON on catastrophic failure
        error_resp = {
            "answer": {"error": "Internal bot exception occurred.", "details": str(e)},
            "log_url": logger.get_log_url()
        }
        await update.message.reply_text(text=json.dumps(error_resp, separators=(',', ':')))


@app.get("/health")
def health():
    return {"status": "ok"}




import asyncio
import os
import requests
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Get your public Render URL from environment variable or default string
APP_URL = os.getenv("BASE_URL", "https://tds-p1-5.onrender.com")

async def keep_alive_loop():
    """Pings the /health endpoint every 10 minutes to prevent Render from sleeping."""
    health_endpoint = f"{APP_URL.rstrip('/')}/health"
    
    # Wait 10 seconds after server starts before the first ping
    await asyncio.sleep(10)
    
    while True:
        try:
            # Send a fast GET request to /health
            response = requests.get(health_endpoint, timeout=10)
            print(f"[Keep-Alive] Pinged {health_endpoint} - Status: {response.status_code}")
        except Exception as err:
            print(f"[Keep-Alive] Ping failed: {err}")
            
        # Sleep for 10 minutes (600 seconds) before pinging again
        await asyncio.sleep(600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the background loop when FastAPI boots
    ping_task = asyncio.create_task(keep_alive_loop())
    yield
    # Shutdown: Cancel the task when server stops
    ping_task.cancel()

# Initialize FastAPI with the lifespan handler
app = FastAPI(lifespan=lifespan)
