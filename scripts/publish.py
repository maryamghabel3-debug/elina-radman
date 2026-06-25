"""
ELINA OS — Publisher
Posts content via Buffer API (FREE tier: 3 channels, 10 queued posts)
Instagram + TikTok + Pinterest
"""

import os
import json
import glob
import requests
from datetime import datetime


def publish(content):
    token = os.environ.get("BUFFER_API_TOKEN", "")
    if not token:
        print("No BUFFER_API_TOKEN")
        return False

    text = content["caption"] + "\n.\n" + content["hashtags"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get profiles from Buffer
    try:
        r = requests.get("https://api.bufferapp.com/1/profiles.json", headers=headers)
        profiles = {p["service"]: p["id"] for p in r.json()}
        print(f"   Profiles: {list(profiles.keys())}")
    except Exception as e:
        print(f"   Buffer error: {e}")
        return False

    platform_map = {
        "instagram": "instagram",
        "tiktok": "tiktok",
        "pinterest": "pinterest",
    }

    results = []
    for plat in content.get("platforms", []):
        service = platform_map.get(plat)
        pid = profiles.get(service)
        if not pid:
            print(f"   ⚠️ No {plat} profile")
            continue

        data = {
            "profile_ids": [pid],
            "text": text,
            "scheduled_at": content.get("scheduled_for", datetime.now().isoformat()),
        }

        try:
            r2 = requests.post(
                "https://api.bufferapp.com/1/updates/create.json",
                headers=headers,
                json=data,
            )
            if r2.status_code == 200:
                print(f"   ✅ {plat}")
                results.append(plat)
            else:
                print(f"   ❌ {plat}: {r2.status_code}")
        except Exception as e:
            print(f"   ❌ {plat}: {e}")

    return len(results) > 0


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
