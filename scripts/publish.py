"""
ELINA OS — Publisher (auto-routing)

Chooses the publishing backend automatically:
  * ZERNIO_API_KEY set  -> Zernio/Late unified API (cloud, free tier, no server)
  * else POSTIZ_API_TOKEN set -> Postiz (self-hosted / cloud)
  * else -> nothing to do (prints a hint)

Both backends publish approved items from content/queue/*.json to Instagram,
TikTok, YouTube, Pinterest, Facebook and more, and only mark a piece as
`published` on a real success response.
"""

import os
import sys

# Make the repo root importable so we can reuse the agent publishers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    print("📤 ELINA OS — Publisher")

    if os.environ.get("ZERNIO_API_KEY"):
        print("   Backend: Zernio/Late (cloud)")
        from agents.publisher_zernio import ZernioPublisher

        result = ZernioPublisher().run()
    elif os.environ.get("POSTIZ_API_TOKEN"):
        print("   Backend: Postiz")
        from agents.publisher import Publisher

        result = Publisher().run()
    else:
        print("   ⚠️  No publishing backend configured.")
        print("   Set ZERNIO_API_KEY (recommended) or POSTIZ_API_TOKEN to enable auto-posting.")
        return

    published = result.get("published", []) if isinstance(result, dict) else []
    if result.get("error"):
        print(f"   ❌ {result['error']}")
    print(f"   ✅ Published {len(published)} item(s)")


if __name__ == "__main__":
    main()
