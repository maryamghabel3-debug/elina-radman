#!/usr/bin/env python3
"""
Test Live Video Generation
Runs DirectorAgent to generate a video shot and sends it to Telegram or git repository.
"""

import os
import sys
import json

# Make repo root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.video_generator import DirectorAgent

def main():
    print("🎬 ElinaOS Live Video Verification...")
    
    agent = DirectorAgent()
    scene = {
        "action": "Elina Radman walking gracefully down a Parisian street wearing a tailored camel trench coat",
        "camera": "Cinematic tracking shot, 35mm lens",
        "lighting": "Golden hour sunlight"
    }
    
    print(f"\n🎬 Generating shot for scene: {json.dumps(scene, ensure_ascii=False)}")
    video_path = agent.generate_video_shot(scene, index=1)
    
    if video_path and os.path.exists(video_path) and os.path.getsize(video_path) > 1000:
        size_kb = os.path.getsize(video_path) / 1024.0
        print(f"\n✅ SUCCESS! Video generated at: {video_path} ({size_kb:.1f} KB)")
        
        # Send to Telegram if configured
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if bot_token and chat_id:
            try:
                import requests
                print("\n📤 Sending generated video directly to your Telegram...")
                with open(video_path, "rb") as fh:
                    cap = f"🎬 ویدیو تستی الینا رادمان\nحجم: {size_kb:.1f} KB"
                    requests.post(
                        f"https://api.telegram.org/bot{bot_token}/sendVideo",
                        data={"chat_id": chat_id, "caption": cap},
                        files={"video": fh},
                        timeout=120,
                    )
                print("✅ Telegram video sent successfully!")
            except Exception as e:
                print(f"⚠️ Could not send Telegram video: {e}")
    else:
        print("\n❌ FAILURE: Could not generate a playable video file.")
        sys.exit(1)

if __name__ == "__main__":
    main()
