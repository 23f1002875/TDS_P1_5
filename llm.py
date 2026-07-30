import os
import json
import httpx
from typing import Dict, Any, Tuple
from openai import AsyncOpenAI

class LLMAgent:
    """Interacts with OpenAI-compatible APIs with event-loop safe client management."""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        # Clean trailing slashes if present
        raw_base = os.getenv("OPENAI_BASE_URL", "https://aipipe.org/openrouter/v1")
        self.base_url = raw_base.rstrip("/")
        self.model = os.getenv("LLM_MODEL", "openai/gpt-4o")

    def _get_client() -> AsyncOpenAI:
        """Dynamically create AsyncOpenAI inside the active request's event loop."""
        return AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True
            )
        )

    async def analyze_and_generate_code(
        self, prompt: str, data_context: str, conversation_history: list = None
    ) -> str:
        """Generates Python code for data analysis."""
        client = self._get_client()
        
        system_prompt = (
            "You are an expert Python Data Analyst. Write pure executable Python code using pandas/numpy "
            "to answer the user query. Assign the final answer dictionary to a global variable named `result`. "
            "Return ONLY python code in ```python ``` blocks."
        )

        messages = [{"role": "system", "content": system_prompt}]
        
        if conversation_history:
            messages.extend(conversation_history)
            
        messages.append({
            "role": "user", 
            "content": f"Context:\n{data_context}\n\nTask:\n{prompt}"
        })

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1
            )
            return response.choices[0].message.content or ""
        finally:
            await client.close()

    async def format_final_json(self, raw_result: Any, user_prompt: str) -> str:
        """Formats intermediate results into clean JSON."""
        client = self._get_client()
        
        system_prompt = (
            "You are a strict JSON formatter. Convert the calculation output into the requested JSON structure. "
            "Return ONLY valid JSON. Do not include markdown codeblocks or extra text."
        )

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"User Prompt: {user_prompt}\nRaw Calculation Output: {raw_result}"}
                ],
                temperature=0.0
            )
            return response.choices[0].message.content or "{}"
        finally:
            await client.close()
