# Telegram Data Analyst Bot

A production-ready Telegram bot that acts as an autonomous data analyst. It handles multi-turn conversations, parses datasets (CSV, JSON, Excel, ZIP, HTML) automatically from URLs or inline text, and executes pandas operations securely using an LLM.

## Project Architecture
- **`app.py`**: FastAPI entry point, handles webhook integration and serves JSONL logs.
- **`bot.py`**: Interacts with the Telegram API and manages multi-turn memory.
- **`agent.py`**: Orchestrates downloading, LLM code generation, code execution, and error handling.
- **`llm.py`**: Interfaces with the OpenAI-compatible API to generate analytical Python code and strictly format output.
- **`tools.py`**: Contains robust dataset downloaders, zip extractors, and secure Python execution context.
- **`logger.py`**: Logs the detailed execution chain of each run into a globally accessible UUID-based JSONL file.

## Setup Instructions

### 1. Telegram BotFather
1. Open Telegram and search for `@BotFather`.
2. Type `/newbot` and follow the steps.
3. Save the HTTP API Token provided.

### 2. OpenAI Key
You will need an API key from OpenAI (or an OpenAI-compatible endpoint like Together, AnyScale).
Save your key.

### 3. Local Environment Setup
```bash
# Clone the repository
git clone <repo-url>
cd <repo-name>

# Copy example environment file
cp .env.example .env

# Edit .env and insert your API keys and tokens
nano .env

# Create virtual environment and install requirements
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
