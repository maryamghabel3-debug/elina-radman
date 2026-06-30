#!/usr/bin/env python3
"""
Test Script for Media Generation (Images & Videos)
This script allows you to manually trigger the creation of a photo or a video
using the Free Cloud GPU integrations (Hugging Face Spaces) we set up.
"""

import os
from agents.platform_managers import VisualCreatorAgent
from agents.video_generator import DirectorAgent

def test_image():
    print("=== Testing Face-Consistent Image Generation ===")
    # Ensure you have your Hugging Face Token set in your environment variables!
    # export HF_TOKEN="hf_your_token_here"
    
    agent = VisualCreatorAgent()
    prompt = "wearing a tailored camel oversized blazer, sitting in a Parisian cafe, drinking coffee, natural sunlight"
    
    output_path = agent.generate_consistent_character(prompt)
    print(f"Result Image Path: {output_path}")

def test_video():
    print("\n=== Testing Video Generation (HunyuanVideo) ===")
    agent = DirectorAgent()
    
    # We pass a simple scene definition to test the cloud video generation
    scene = {
        "camera": "Medium Close-up, cinematic",
        "lighting": "Golden hour lighting",
        "action": "Elina walking gracefully down the street, looking at the camera, wearing neutral tones",
    }
    
    output_path = agent.generate_video_shot(scene, index=99)
    print(f"Result Video Path: {output_path}")

if __name__ == "__main__":
    print("Welcome to ElinaOS Media Tester!")
    print("Note: You MUST set your 'HF_TOKEN' environment variable for this to work.")
    print("If HF_TOKEN is not set, the system will return a 'mock' file.")
    
    print("\n1. Test Image")
    print("2. Test Video")
    choice = input("Enter choice (1/2): ")
    
    if choice == "1":
        test_image()
    elif choice == "2":
        test_video()
    else:
        print("Invalid choice.")
