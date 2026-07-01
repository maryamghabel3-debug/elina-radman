#!/usr/bin/env python3
"""
ElinaOS - Master Run Script
Run this file to start the Streamlit Dashboard for managing Elina locally.
"""
import os
import subprocess

def check_dependencies():
    print("Checking dependencies...")
    try:
        import streamlit
    except ImportError:
        print("Installing required packages...")
        os.system("pip install -r requirements.txt")
        
def start_dashboard():
    print("🌿 Starting ElinaOS Dashboard...")
    print("If it doesn't open automatically, click the link below (e.g. http://localhost:8501)")
    
    # Path to the streamlit app
    app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard", "app.py")
    
    # Run streamlit
    subprocess.run(["streamlit", "run", app_path])

if __name__ == "__main__":
    check_dependencies()
    start_dashboard()
