import os
import json
import asyncio
import requests
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)

from agent import DataAnalystAgent
from logger import RunLogger

# ----------------------------------------------------
# Environment Variables & Configuration
# ----------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("BASE_URL", os.getenv("RENDER_EXTERNAL_URL", "https://tds-p1-5.onrender.com"))

# In-memory dictionary for conversational history
# Structure: user_id -> [{"role": "user"/"assistant", "content": "..."}]
user_memories = defaultdict(list)

# Single agent instance
agent = DataAnalystAgent()


# ----------------------------------------------------
# Telegram Bot Handlers
# ----------------------------------------------------
async def start_command(update: Update, context: CallbackContext) -> None:
    """Handles the /start command."""
    user_id = update.effective_user.id
    user_memories[user_id] = []
    
    instructions = (
        "Hello! I am a Data Analyst Bot.\n"
        "Send me URLs to datasets (CSV, JSON, Excel, ZIP), inline tables, or plain questions.\n"
        "Include the EXACT JSON structure you want me to reply with in your message."
    )
    await update.message.reply_text(instructions)


async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handles normal text messages."""
    user_id = update.effective_user.id
    user_text = update.message.text

    # 1. Update user memory
    user_memories[user_id].append({"role": "user", "content": user_text})
    
    logger = RunLogger(APP_URL)

    try:
        # 2. Process query with agent
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


# ----------------------------------------------------
# Background Keep-Alive Task
# ----------------------------------------------------
async def keep_alive_loop():
    """Pings the /health endpoint every 10 minutes to prevent Render from sleeping."""
    health_endpoint = f"{APP_URL.rstrip('/')}/health"
    await asyncio.sleep(10)  # Short pause on startup
    
    while True:
        try:
            response = requests.get(health_endpoint, timeout=10)
            print(f"[Keep-Alive] Pinged {health_endpoint} - Status: {response.status_code}")
        except Exception as err:
            print(f"[Keep-Alive] Ping failed: {err}")
            
        await asyncio.sleep(600)  # Sleep 10 minutes


# ----------------------------------------------------
# FastAPI Lifespan (Starts Telegram + Keep-Alive)
# ----------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Build and start Telegram Bot Long-Polling
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start_command))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()
    print("[System] Telegram Bot Polling started.")

    # 2. Start Keep-Alive Ping Task
    ping_task = asyncio.create_task(keep_alive_loop())
    print("[System] Keep-Alive loop started.")

    yield  # Server runs here

    # 3. Shutdown sequence
    ping_task.cancel()
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()
    print("[System] Telegram Bot and background tasks stopped.")


# ----------------------------------------------------
# App Initialization & Endpoints
# ----------------------------------------------------
app = FastAPI(lifespan=lifespan)

# Expose logs directory publicly so log_url works with wget
if os.path.exists("logs"):
    app.mount("/logs", StaticFiles(directory="logs"), name="logs")

@app.get("/health")
def health():
    return {"status": "ok"}
