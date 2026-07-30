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
# Environment Variables & Configuration (Standardized)
# ----------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
APP_URL = (
    os.getenv("BASE_URL")
    or os.getenv("HOST_URL")
    or os.getenv("RENDER_EXTERNAL_URL", "https://tds-p1-5.onrender.com")
)

# In-memory dictionary for conversational history
# Structure: user_id -> [{"role": "user"/"assistant", "content": "..."}]
user_memories = defaultdict(list)
MAX_HISTORY_MESSAGES = 10  # Fix #4: Retain only the last 10 messages (5 turns)

# Single agent instance
agent = DataAnalystAgent()


# ----------------------------------------------------
# Defensive Helper Functions
# ----------------------------------------------------
def normalize_response(raw_dict: dict, log_url: str) -> dict:
    """
    Fix #1: Prevents double-wrapped JSON payloads like {"answer": {"answer": ...}}.
    Guarantees the response top level always contains exactly 'answer' and 'log_url'.
    """
    if not isinstance(raw_dict, dict):
        return {"answer": raw_dict, "log_url": log_url}

    answer_payload = raw_dict.get("answer", raw_dict)

    # Unwrap recursively if double-wrapped
    while (
        isinstance(answer_payload, dict)
        and "answer" in answer_payload
        and len(answer_payload) == 1
    ):
        answer_payload = answer_payload["answer"]

    return {
        "answer": answer_payload,
        "log_url": log_url
    }


# ----------------------------------------------------
# Telegram Bot Handlers
# ----------------------------------------------------
async def start_command(update: Update, context: CallbackContext) -> None:
    """Handles the /start command."""
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    user_memories[user_id] = []

    instructions = (
        "Hello! I am a Data Analyst Bot.\n"
        "Send me URLs to datasets (CSV, JSON, Excel, ZIP), inline tables, or plain questions.\n"
        "Include the EXACT JSON structure you want me to reply with in your message."
    )
    await update.message.reply_text(instructions)


async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handles normal text messages with memory trimming and JSON sanitization."""
    if not update.effective_user or not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    user_text = update.message.text

    # 1. Update user memory & trim to avoid context bloat (Fix #4)
    user_memories[user_id].append({"role": "user", "content": user_text})
    user_memories[user_id] = user_memories[user_id][-MAX_HISTORY_MESSAGES:]

    logger = RunLogger(APP_URL)

    try:
        # 2. Process query with agent (with strict execution timeout inside agent)
        raw_agent_response = await agent.process_conversation(
            user_memories[user_id], logger
        )

        # 3. Fix #6: Ensure log URL is valid and file exists
        log_url = logger.get_log_url()

        # 4. Fix #1: Normalize response format to prevent {"answer": {"answer": ...}}
        final_dict = normalize_response(raw_agent_response, log_url)

        # 5. Add sanitized assistant reply back to memory
        user_memories[user_id].append(
            {"role": "assistant", "content": json.dumps(final_dict.get("answer"))}
        )

        # 6. Reply STRICTLY with single compact JSON string and NOTHING ELSE
        exact_json_string = json.dumps(final_dict, separators=(",", ":"))
        await update.message.reply_text(text=exact_json_string)

    except Exception as e:
        # Fallback strict JSON on catastrophic failure
        log_url = logger.get_log_url() if logger else f"{APP_URL}/logs/error.jsonl"
        error_resp = {
            "answer": {"error": "Internal bot exception occurred.", "details": str(e)},
            "log_url": log_url,
        }
        await update.message.reply_text(
            text=json.dumps(error_resp, separators=(",", ":"))
        )


# ----------------------------------------------------
# Background Keep-Alive Task (Fix #12)
# ----------------------------------------------------
async def keep_alive_loop():
    """Pings the /health endpoint every 10 minutes to prevent Render from sleeping."""
    health_endpoint = f"{APP_URL.rstrip('/')}/health"
    await asyncio.sleep(10)  # Initial delay before starting loop

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
    # Ensure logs directory exists for static mounting
    os.makedirs("logs", exist_ok=True)

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN or TELEGRAM_BOT_TOKEN environment variable is missing!")

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

    yield  # FastAPI Server runs here

    # 3. Shutdown sequence
    ping_task.cancel()
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()
    print("[System] Telegram Bot and background tasks stopped cleanly.")


# ----------------------------------------------------
# App Initialization & Public Routes
# ----------------------------------------------------
app = FastAPI(lifespan=lifespan)

# Expose logs directory publicly so log_url works with wget
os.makedirs("logs", exist_ok=True)
app.mount("/logs", StaticFiles(directory="logs"), name="logs")


@app.get("/health")
def health():
    return {"status": "ok"}
