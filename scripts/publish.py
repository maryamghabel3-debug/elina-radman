"""
ELINA OS — Publisher
Posts content via Postiz API (Open Source, Self-Hostable, 100% Free)
Instagram + TikTok + Pinterest + YouTube + LinkedIn and more!
"""

import os
import json
import glob
import requests
from datetime import datetime


def publish(content):
    postiz_url = os.environ.get("POSTIZ_URL", "http://localhost:3000/api")
    token = os.environ.get("POSTIZ_API_TOKEN", "")
    
    if not token:
        print("No POSTIZ_API_TOKEN")
        return False

    text = content["caption"] + "\n.\n" + content["hashtags"]
    platforms = content.get("platforms", ["instagram", "tiktok", "youtube"])
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "content": text,
        "platforms": platforms,
        "scheduled_at": content.get("scheduled_for", datetime.now().isoformat())
    }

    try:
        print(f"   Scheduling on Postiz for platforms: {platforms}...")
        r2 = requests.post(f"{postiz_url}/posts", headers=headers, json=payload)
        
        if r2.status_code in [200, 201]:
            print(f"   ✅ Published successfully via Postiz!")
            return True
        else:
            print(f"   ❌ Postiz Error: {r2.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Postiz Exception: {e}")
        return False


def main():
    print("📤 ELINA OS — Publisher")

    queue = "content/queue"
    if not os.path.isdir(queue):
        print("No queue")
        return

    for fp in sorted(glob.glob(f"{queue}/*.json")):
        with open(fp) as f:
            pieces = json.load(f)

        changed = False
        for c in pieces:
            if c.get("status") == "approved":
                print(f"📤 {c['id']}")
                if publish(c):
                    c["status"] = "published"
                    c["published_at"] = datetime.now().isoformat()
                    changed = True

        if changed:
            with open(fp, "w") as f:
                json.dump(pieces, f, indent=2)
            print(f"   💾 Updated {fp}")


if __name__ == "__main__":
    main()
