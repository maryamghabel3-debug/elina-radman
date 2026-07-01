"""ZernioPublisher — Posts approved content via the Zernio/Late unified API.

Zernio (formerly getlate.dev) exposes ONE REST API that fans a single post out
to Instagram, TikTok, YouTube, Pinterest, Facebook and 10+ more platforms. The
free tier allows 2 connected accounts with unlimited posts and full API access,
which makes it the quickest zero-server way to give Elina real auto-publishing.

Setup (done once by the user):
  1. Sign up at https://zernio.com and connect Elina's social accounts.
  2. Settings -> API Keys -> Create API Key  (starts with `sk_`).
  3. Add it to GitHub Secrets as ZERNIO_API_KEY.

The agent maps Elina's queue items to Zernio's schema and only marks a piece as
`published` on a real success response, mirroring the safety of the Postiz
publisher. It degrades gracefully: missing key -> clean error, never a crash.
"""

from .base import Agent
from datetime import datetime
import os
import json
import glob
import requests

_BASE_URL = os.environ.get("ZERNIO_BASE_URL", "https://zernio.com/api/v1")

# Map the platform names Elina uses internally -> Zernio API platform values.
# Platforms Zernio doesn't support (e.g. lemon8, threads-only variants) are
# dropped silently so a post still goes out to the supported ones.
_PLATFORM_MAP = {
    "instagram": "instagram",
    "tiktok": "tiktok",
    "youtube": "youtube",
    "pinterest": "pinterest",
    "facebook": "facebook",
    "twitter": "twitter",
    "x": "twitter",
    "linkedin": "linkedin",
    "threads": "threads",
    "reddit": "reddit",
    "bluesky": "bluesky",
    "telegram": "telegram",
}


class ZernioPublisher(Agent):
    def __init__(self):
        super().__init__(
            "ZernioPublisher", "Publishes content to many platforms via the Zernio/Late API"
        )
        self.token = os.environ.get("ZERNIO_API_KEY", "")
        self.timezone = os.environ.get("ELINA_TIMEZONE", "Asia/Shanghai")
        self.session = requests.Session()
        if self.token:
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                }
            )

    # ------------------------------------------------------------------ #
    def list_accounts(self) -> list:
        """Return the connected social accounts (each has _id + platform)."""
        try:
            r = self.session.get(f"{_BASE_URL}/accounts", timeout=20)
            r.raise_for_status()
            data = r.json()
            return data.get("accounts", data if isinstance(data, list) else [])
        except (requests.RequestException, ValueError) as e:
            self.log(f"Could not list Zernio accounts: {e}", "error")
            return []

    def _account_map(self) -> dict:
        """platform -> accountId, so a queue item's platform list can be resolved."""
        mapping = {}
        for acc in self.list_accounts():
            plat = (acc.get("platform") or "").lower()
            acc_id = acc.get("_id") or acc.get("id")
            if plat and acc_id and plat not in mapping:
                mapping[plat] = acc_id
        return mapping

    def _resolve_platforms(self, wanted: list, account_map: dict) -> list:
        """Build Zernio's platforms[] payload from Elina's platform names."""
        out = []
        for name in wanted:
            zern = _PLATFORM_MAP.get(str(name).lower())
            if not zern:
                continue
            acc_id = account_map.get(zern)
            if acc_id:
                out.append({"platform": zern, "accountId": acc_id})
        return out

    # ------------------------------------------------------------------ #
    def run(self) -> dict:
        self.runs += 1
        self.last_run = datetime.now().isoformat()

        if not self.token:
            self.log("No ZERNIO_API_KEY", "error")
            return {"error": "no_token"}

        account_map = self._account_map()
        if not account_map:
            self.log("No connected Zernio accounts (connect them in the dashboard)", "error")
            return {"error": "no_accounts"}

        published = []

        for fp in sorted(glob.glob("content/queue/*.json")):
            with open(fp) as f:
                pieces = json.load(f)
            changed = False
            for c in pieces:
                if c.get("status") != "approved":
                    continue

                text = c.get("caption", "")
                if c.get("hashtags"):
                    text += "\n.\n" + c["hashtags"]

                wanted = c.get("platforms", ["instagram", "tiktok"])
                platforms = self._resolve_platforms(wanted, account_map)
                if not platforms:
                    self.log(
                        f"Skipping {c.get('id')}: none of {wanted} are connected on Zernio",
                        "error",
                    )
                    continue

                payload = {
                    "content": text,
                    "scheduledFor": c.get("scheduled_for", datetime.now().isoformat()),
                    "timezone": self.timezone,
                    "platforms": platforms,
                }
                # Attach media if the piece references an image/video URL
                media = c.get("media_url") or c.get("image")
                if media:
                    payload["mediaUrls"] = [media]

                try:
                    r = self.session.post(f"{_BASE_URL}/posts", json=payload, timeout=30)
                except requests.RequestException as e:
                    self.log(f"Post failed via Zernio: {e}", "error")
                    continue

                if r.status_code in (200, 201):
                    plats = [p["platform"] for p in platforms]
                    self.log(f"Posted {c.get('id')} to {plats} via Zernio")
                    published.append({"id": c.get("id", "1"), "platforms": plats})
                    c["status"] = "published"
                    c["published_at"] = datetime.now().isoformat()
                    c["published_via"] = "zernio"
                    changed = True
                else:
                    self.log(
                        f"Zernio rejected {c.get('id')}: HTTP {r.status_code} {r.text[:150]}",
                        "error",
                    )
                    c["status"] = "failed"
                    c["last_error"] = f"HTTP {r.status_code}"
                    changed = True

            if changed:
                with open(fp, "w") as f:
                    json.dump(pieces, f, indent=2, ensure_ascii=False)

        self.log(f"Published {len(published)} items via Zernio")
        return {"published": published}


if __name__ == "__main__":
    print(json.dumps(ZernioPublisher().run(), indent=2, ensure_ascii=False))
