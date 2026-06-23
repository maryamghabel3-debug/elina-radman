"""Publisher Agent — Posts to social platforms via Buffer"""
from .base import Agent
from datetime import datetime
import os, json, glob, requests

class Publisher(Agent):
    def __init__(self):
        super().__init__("Publisher", "Posts content to social media")
    
    def run(self):
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        token = os.environ.get("BUFFER_API_TOKEN","")
        if not token:
            self.log("No BUFFER_API_TOKEN", "error")
            return {"error": "no_token"}
        
        headers = {"Authorization": f"Bearer {token}"}
        try:
            r = requests.get("https://api.bufferapp.com/1/profiles.json", headers=headers)
            profiles = {p["service"]: p["id"] for p in r.json()}
        except Exception as e:
            self.log(f"Buffer connect failed: {e}", "error")
            return {"error": str(e)}
        
        platform_map = {"instagram":"instagram","tiktok":"tiktok","pinterest":"pinterest"}
        published = []
        
        for fp in sorted(glob.glob("content/queue/*.json")):
            with open(fp) as f:
                pieces = json.load(f)
            changed = False
            for c in pieces:
                if c.get("status") != "approved":
                    continue
                text = c["caption"] + "\n.\n" + c["hashtags"]
                for plat in c.get("platforms",[]):
                    sid = platform_map.get(plat)
                    pid = profiles.get(sid)
                    if not pid: continue
                    data = {"profile_ids":[pid],"text":text,
                            "scheduled_at": c.get("scheduled_for", datetime.now().isoformat())}
                    try:
                        r2 = requests.post("https://api.bufferapp.com/1/updates/create.json",
                                         headers=headers, json=data)
                        if r2.status_code == 200:
                            self.log(f"Posted to {plat}")
                            published.append({"id":c["id"],"platform":plat})
                    except Exception as e:
                        self.log(f"Post failed {plat}: {e}","error")
                c["status"] = "published"
                c["published_at"] = datetime.now().isoformat()
                changed = True
            if changed:
                with open(fp,"w") as f:
                    json.dump(pieces, f, indent=2)
        
        self.log(f"Published {len(published)} items")
        return {"published": published}
