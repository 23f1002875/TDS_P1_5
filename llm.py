import os
import json
import re
import asyncio
import requests
from typing import Any

class LLMAgent:
    """Interacts with OpenAI-compatible APIs, dynamically reading environment variables per request."""
    
    @property
    def api_key(self) -> str:
        return os.getenv("OPENAI_API_KEY", "").strip(' "\'')

    @property
    def base_url(self) -> str:
        raw_base = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        match = re.search(r'https?://[^\s\)\]]+', raw_base)
        if match:
            return match.group(0).rstrip("/")
        return raw_base.strip(' "\'').rstrip("/")

    @property
    def model(self) -> str:
        # Defaults to free OpenRouter router if LLM_MODEL is not set
        return os.getenv("LLM_MODEL", "openrouter/free").strip(' "\'')

    def _make_request(self, messages: list, temperature: float = 0.0) -> str:
        """Synchronous HTTP call executed in a thread pool with dynamic settings."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            raise RuntimeError(
                f"API Error ({response.status_code}) using model '{self.model}': {response.text}"
            )
            
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    async def generate_python_code(self, query: str, datasets_info: str) -> str:
        """Generates pandas code to answer the user query."""
        system_prompt = (
            "You are an expert Python data analyst.\n"
            "You have access to a dictionary named `dfs` which maps filenames to pandas DataFrames.\n"
            "Datasets currently loaded: " + datasets_info + "\n\n"
            "Write valid Python code using pandas to solve the user's latest query.\n"
            "Store your final output in a variable named exactly `result_data`.\n"
            "If the dataset is inline (markdown/json/csv in the text), parse it using io.StringIO and pandas.\n"
            "Reply ONLY with raw python code. No explanations. No markdown formatting backticks."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]

        return await asyncio.to_thread(self._make_request, messages, 0.0)

    async def format_final_answer(self, user_query: str, raw_result: Any) -> str:
        """Formats raw calculated output into the user's requested JSON shape."""
        system_prompt = (
            "You are a strict JSON formatter. The user requested an answer to a question, "
            "and also provided a desired JSON schema or format.\n"
            "I will give you the raw calculated result. "
            "You must return ONLY valid JSON matching their requested shape with the calculated result.\n"
            "Never invent keys they didn't ask for. Never wrap the output in markdown backticks. "
            "Return raw JSON string strictly."
        )
        
        user_prompt = f"User's request: {user_query}\n\nRaw Computed Result: {str(raw_result)}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return await asyncio.to_thread(self._make_request, messages, 0.0)
