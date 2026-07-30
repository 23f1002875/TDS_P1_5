import os
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot import start_command, handle_message

# Telegram Application Instance
tg_app = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
tg_app.add_handler(CommandHandler("start", start_command))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI to start and stop Telegram webhook."""
    await tg_app.initialize()
    await tg_app.start()
    
    host_url = os.getenv("HOST_URL", os.getenv("RENDER_EXTERNAL_URL", ""))
    if host_url:
        webhook_url = f"{host_url.rstrip('/')}/webhook"
        await tg_app.bot.set_webhook(url=webhook_url)
        print(f"Webhook set to {webhook_url}")
    else:
        print("Warning: HOST_URL not set. Webhook not configured.")
        
    yield
    
    await tg_app.stop()
    await tg_app.shutdown()

app = FastAPI(lifespan=lifespan)

# Mount logs directory so JSONL files are publicly downloadable
os.makedirs("logs", exist_ok=True)
app.mount("/logs", StaticFiles(directory="logs"), name="logs")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Endpoint for Telegram to send updates."""
    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"status": "ok"}

@app.get("/")
def health_check():
    """Simple health check endpoint."""
    return {"status": "Service is running."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
