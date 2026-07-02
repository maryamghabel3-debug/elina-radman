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
        
    concept = "wearing a tailored camel trench coat, Parisian cafe terrace, smiling softly, natural morning sunlight"
    print(f"\n🎨 Generating live image for concept: '{concept}'...")
    
    result = studio.generate(concept=concept)
    
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
    else:
        print(f"\n❌ FAILURE: Could not generate image. Error: {result.get('error')}")

if __name__ == "__main__":
    main()
