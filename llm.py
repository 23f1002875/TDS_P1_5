import os
import json
import httpx
from typing import Any
from openai import AsyncOpenAI

class LLMAgent:
    """Interacts with OpenAI-compatible APIs using event-loop safe client management."""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        raw_base = os.getenv("OPENAI_BASE_URL", "https://aipipe.org/openrouter/v1")
        self.base_url = raw_base.rstrip("/")
        self.model = os.getenv("LLM_MODEL", "openai/gpt-4o")

    def _get_client(self) -> AsyncOpenAI:
        """Dynamically creates AsyncOpenAI inside the active request's event loop."""
        return AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True
            )
        )

    async def generate_python_code(self, query: str, datasets_info: str) -> str:
        """Generates pandas code to answer the query."""
        system_prompt = (
            "You are an expert Python data analyst.\n"
            "You have access to a dictionary named `dfs` which maps filenames to pandas DataFrames.\n"
            "Datasets currently loaded: " + datasets_info + "\n\n"
            "Write valid Python code using pandas to solve the user's latest query.\n"
            "Store your final output in a variable named exactly `result_data`.\n"
            "If the dataset is inline (markdown/json/csv in the text), parse it using io.StringIO and pandas.\n"
            "Reply ONLY with raw python code. No explanations. No markdown formatting backticks."
        )

        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.0,
            )
            return response.choices[0].message.content.strip()
        finally:
            await client.close()

    async def format_final_answer(self, user_query: str, raw_result: Any) -> str:
        """Formats the raw result into the user's requested JSON shape."""
        system_prompt = (
            "You are a strict JSON formatter. The user requested an answer to a question, "
            "and also provided a desired JSON schema or format.\n"
            "I will give you the raw calculated result. "
            "You must return ONLY valid JSON matching their requested shape with the calculated result.\n"
            "Never invent keys they didn't ask for. Never wrap the output in markdown backticks. "
            "Return raw JSON string strictly."
        )
        
        user_prompt = f"User's request: {user_query}\n\nRaw Computed Result: {str(raw_result)}"

        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0
            )
            return response.choices[0].message.content.strip()
        finally:
            await client.close()
