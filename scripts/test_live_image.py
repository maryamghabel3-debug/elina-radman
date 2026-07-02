#!/usr/bin/env python3
"""
Test Live Image Generation (Face Consistency Check)
Runs ImageStudio with current environment variables (HF_TOKEN / GEMINI_API_KEY)
and outputs verification report.
"""

import os
import sys
import json

# Make repo root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.image_studio import ImageStudio

def main():
    print("🕊️ ElinaOS Live Image Verification...")
    hf_token = os.environ.get("HF_TOKEN", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    
    print(f"HF_TOKEN available: {'YES (Length: ' + str(len(hf_token)) + ')' if hf_token else 'NO'}")
    print(f"GEMINI_API_KEY available: {'YES' if gemini_key else 'NO'}")
    
    studio = ImageStudio()
    refs = studio.reference_images()
    print(f"Discovered reference face images: {len(refs)}")
    if refs:
        print(f"Primary reference: {refs[0]}")
        
    concept = "sitting at a Parisian street cafe terrace, wearing chic camel wide-leg pleated trousers and tailored blazer, golden morning sunlight, candid lifestyle"
    print(f"\n🎨 Generating live image for concept: '{concept}'...")
    
    result = studio.generate(concept=concept, prefer="auto")
    
    print("\n=== GENERATION REPORT ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if result.get("path") and os.path.exists(result["path"]):
        size_kb = os.path.getsize(result["path"]) / 1024.0
        print(f"\n✅ SUCCESS! Image written to: {result['path']} ({size_kb:.1f} KB)")
        print(f"Provider used: {result.get('provider')}")
        print(f"Used face reference: {result.get('used_reference')}")
        if result.get("used_reference"):
            print("🌟 VERIFIED: The image was generated using Elina's reference face!")
        else:
            print("⚠️ WARNING: The image was generated without a face reference.")

        # Send to Telegram if configured
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if bot_token and chat_id:
            try:
                import requests
                print("\n📤 Sending test photo directly to your Telegram...")
                with open(result["path"], "rb") as fh:
                    cap = f"🖼 تست زنده عکس الینا (Provider: {result.get('provider')})\nثبات چهره مرجع: {'✅ بله' if result.get('used_reference') else '⚠️ خیر'}"
                    requests.post(
                        f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                        data={"chat_id": chat_id, "caption": cap},
                        files={"photo": fh},
                        timeout=60,
                    )
                print("✅ Telegram photo sent successfully!")
            except Exception as e:
                print(f"⚠️ Could not send Telegram photo: {e}")
    else:
        print(f"\n❌ FAILURE: Could not generate image. Error: {result.get('error')}")
        sys.exit(1)

if __name__ == "__main__":
    main()
