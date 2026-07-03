#!/usr/bin/env python3
"""Diagnostic: lists which Gemini models are actually available/callable for
the configured GEMINI_API_KEY, and which of those support image generation.

Usage:
    GEMINI_API_KEY=xxx python scripts/list_gemini_models.py
"""
import os
import sys
import json
import requests

API_KEY = os.environ.get("GEMINI_API_KEY", "")

def main():
    if not API_KEY:
        print("❌ GEMINI_API_KEY not set in environment.")
        sys.exit(1)

    url = "https://generativelanguage.googleapis.com/v1beta/models"
    r = requests.get(url, headers={"x-goog-api-key": API_KEY}, timeout=30)
    print(f"HTTP {r.status_code}")
    if r.status_code != 200:
        print(r.text[:2000])
        sys.exit(1)

    data = r.json()
    models = data.get("models", [])
    print(f"\n✅ Found {len(models)} models available for this key.\n")

    image_capable = []
    text_capable = []
    for m in models:
        name = m.get("name", "").replace("models/", "")
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue
        # Heuristic: models with "image" in the name are image-generation capable
        if "image" in name.lower():
            image_capable.append(name)
        else:
            text_capable.append(name)

    print("🎨 IMAGE-CAPABLE models (name contains 'image'):")
    for n in image_capable:
        print(f"   - {n}")
    if not image_capable:
        print("   (none found)")

    print(f"\n📝 Other text/general models ({len(text_capable)} total, showing first 15):")
    for n in text_capable[:15]:
        print(f"   - {n}")

    # Save full raw list for reference
    out_path = "content/gemini_models_report.json"
    os.makedirs("content", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"image_capable": image_capable, "all_models": [m.get("name") for m in models]}, f, indent=2)
    print(f"\n💾 Full report saved to {out_path}")

    # Now actually TRY generating a tiny test image with each image-capable model
    if image_capable:
        print("\n🧪 Testing actual image generation on each image-capable model...")
        for model_id in image_capable:
            test_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
            payload = {
                "contents": [{"parts": [{"text": "A simple red circle on white background"}]}],
                "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
            }
            try:
                resp = requests.post(
                    test_url,
                    headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
                    json=payload,
                    timeout=60,
                )
                if resp.status_code == 200:
                    rjson = resp.json()
                    has_image = False
                    for cand in rjson.get("candidates", []):
                        for part in cand.get("content", {}).get("parts", []):
                            if part.get("inline_data") or part.get("inlineData"):
                                has_image = True
                    status = "✅ WORKS (returned image)" if has_image else "⚠️ 200 OK but no image part"
                else:
                    status = f"❌ HTTP {resp.status_code}: {resp.text[:150]}"
            except Exception as e:
                status = f"❌ Exception: {e}"
            print(f"   {model_id}: {status}")

if __name__ == "__main__":
    main()
