"""Base agent class"""
import json, os, uuid
from datetime import datetime
from typing import Dict, Any, Optional

class Agent:
    def __init__(self, name: str, desc: str):
        self.name = name
        self.desc = desc
        self.id = f"{name.lower().replace(' ','_')}_{uuid.uuid4().hex[:6]}"
        self.created = datetime.now().isoformat()
        self.last_run: Optional[str] = None
        self.runs = 0
        self.errors = []
    
    def log(self, msg: str, level: str = "info"):
        t = datetime.now().isoformat()
        entry = {"agent": self.name, "time": t, "msg": msg, "level": level}
        if level == "error":
            self.errors.append(msg)
        print(f"[{level.upper()}] {self.name}: {msg}")
        return entry
    
    def status(self) -> Dict:
        return {"name": self.name, "id": self.id, "runs": self.runs, 
                "last_run": self.last_run, "errors": len(self.errors)}
    
    def run(self, *args, **kwargs) -> Any:
        raise NotImplementedError
