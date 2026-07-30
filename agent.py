import json
from typing import List, Dict
from llm import LLMAgent
from logger import RunLogger
from tools import extract_urls, download_and_extract, execute_python

class DataAnalystAgent:
    """Orchestrates data downloading, LLM code generation, and execution."""
    
    def __init__(self):
        self.llm = LLMAgent()

    async def process_conversation(self, conversation: List[Dict[str, str]], logger: RunLogger) -> dict:
        """
        Analyzes the conversation, processes URLs, executes data reasoning, 
        and returns the strictly requested JSON object.
        """
        # We only answer the LAST question, but use context
        last_message = conversation[-1]["content"]
        full_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation])
        
        # 1. Detect and download datasets
        urls = extract_urls(full_context)
        dfs = {}
        for url in urls:
            dfs.update(download_and_extract(url))
        
        dataset_info = ", ".join([f"'{k}': DataFrame({v.shape[0]} rows, {v.shape[1]} cols)" for k, v in dfs.items()])
        if not dataset_info:
            dataset_info = "No external datasets loaded. Look for inline data in the prompt."

        # 2. Planning and Code Generation Loop (with auto-retry)
        max_retries = 3
        success = False
        raw_result = None
        python_code = ""
        error_msg = ""
        
        for attempt in range(max_retries):
            retry_context = full_context
            if error_msg:
                retry_context += f"\n\nSystem: Your previous code failed with error:\n{error_msg}\nPlease fix the code."
                
            python_code = await self.llm.generate_python_code(retry_context, dataset_info)
            
            success, stdout, raw_result = execute_python(python_code, dfs)
            if success:
                break
            else:
                error_msg = stdout # `stdout` holds the exception string on failure

        # 3. Format result strictly to user's JSON instruction
        if success:
            reasoning = "Code executed successfully."
            formatted_json_str = await self.llm.format_final_answer(last_message, raw_result)
        else:
            reasoning = "Failed to execute code after multiple retries."
            formatted_json_str = await self.llm.format_final_answer(last_message, {"error": "Analysis failed", "details": error_msg})

        # Try parsing LLM output to guarantee it's a dict
        try:
            final_answer_dict = json.loads(formatted_json_str)
        except json.JSONDecodeError:
            # Fallback if LLM fails strict JSON
            final_answer_dict = {"answer": formatted_json_str}

        # 4. Log the run
        logger.log(
            user_message=last_message,
            tool="python_pandas",
            dataset_url=", ".join(urls),
            reasoning=reasoning,
            python_code=python_code,
            final_answer=final_answer_dict
        )

        # 5. Construct the final Telegram reply payload
        # "Only wrap it as { 'answer': <requested structure>, 'log_url': ... }"
        return {
            "answer": final_answer_dict,
            "log_url": logger.get_log_url()
        }
