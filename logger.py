import json
import os
import uuid
from datetime import datetime
from typing import Any

class RunLogger:
    """
    Logs agent execution runs into publicly accessible JSONL files.
    """
    def __init__(self, host_url: str):
        self.run_id = str(uuid.uuid4())
        self.log_dir = "logs"
        os.makedirs(self.log_dir, exist_ok=True)
        self.filename = f"run_{self.run_id}.jsonl"
        self.filepath = os.path.join(self.log_dir, self.filename)
        
        base_url = host_url.rstrip('/')
        self.log_url = f"{base_url}/logs/{self.filename}"

    def log(self, user_message: str, tool: str, dataset_url: str, reasoning: str, python_code: str, final_answer: Any) -> None:
        """
        Appends a JSON object to the JSONL log file.
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_message": user_message,
            "tool": tool,
            "dataset_url": dataset_url,
            "reasoning_summary": reasoning,
            "python_execution": python_code,
            "final_answer": final_answer
        }
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def get_log_url(self) -> str:
        """Returns the public URL to access this log."""
        return self.log_url
