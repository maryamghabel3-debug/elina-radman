"""Publisher Agent — Posts to social platforms via Postiz (Unlimited & Free)"""

from .base import Agent
from datetime import datetime
import os
import json
import glob
import requests


class Publisher(Agent):
    def __init__(self):
        super().__init__("Publisher", "Posts content to social media")

    def run(self):
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        postiz_url = os.environ.get("POSTIZ_URL", "http://localhost:3000/api")
        token = os.environ.get("POSTIZ_API_TOKEN", "")
        if not token:
            self.log("No POSTIZ_API_TOKEN", "error")
            return {"error": "no_token"}

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        published = []

        for fp in sorted(glob.glob("content/queue/*.json")):
            with open(fp) as f:
                pieces = json.load(f)
            changed = False
            for c in pieces:
                if c.get("status") != "approved":
                    continue
                
                text = c["caption"] + "\n.\n" + c["hashtags"]
                platforms = c.get("platforms", ["instagram", "tiktok"])
                
                data = {
                    "content": text,
                    "platforms": platforms,
                    "scheduled_at": c.get("scheduled_for", datetime.now().isoformat())
                }
                
                try:
                    # Request to Postiz
                    r2 = requests.post(f"{postiz_url}/posts", headers=headers, json=data)
                    self.log(f"Posted to {platforms} via Postiz")
                    published.append({"id": c.get("id", "1"), "platforms": platforms})
                except Exception as e:
                    self.log(f"Post failed via Postiz: {e}", "error")
                    
                c["status"] = "published"
                c["published_at"] = datetime.now().isoformat()
                changed = True
                
            if changed:
                with open(fp, "w") as f:
                    json.dump(pieces, f, indent=2)

        self.log(f"Published {len(published)} items")
        return {"published": published}
