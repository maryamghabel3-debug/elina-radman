#!/usr/bin/env python
import os
import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agents.audio.freesound_provider import FreesoundProvider


def main():
    parser = argparse.ArgumentParser(description="Diagnose Freesound API Provider")
    parser.add_argument("--query", default="rain", help="Query search term")
    args = parser.parse_args()

    api_key = os.environ.get("FREESOUND_API_KEY") or os.environ.get("FREESOUND_CLIENT_SECRET")
    if not api_key:
        print("Error: Missing FREESOUND_API_KEY or FREESOUND_CLIENT_SECRET in environment.", file=sys.stderr)
        print("FREESOUND_LIVE_SMOKE_FAILED", file=sys.stderr)
        sys.exit(1)

    print("Checking Freesound Provider Diagnostics...")
    print(f"Attempting query: '{args.query}'")

    try:
        provider = FreesoundProvider()
        print("authentication succeeded: YES")
    except Exception as e:
        print("authentication succeeded: NO")
        print(f"Error during initialization: {e}", file=sys.stderr)
        print("FREESOUND_LIVE_SMOKE_FAILED", file=sys.stderr)
        sys.exit(1)

    try:
        results = provider.search(args.query, max_duration_sec=15.0)
        print("HTTP request succeeded: YES")
        print(f"result count: {len(results)}")
        
        # Display top 3 results
        for idx, res in enumerate(results[:3]):
            print(f"Result #{idx+1}:")
            print(f"  ID: {res.external_id}")
            print(f"  Name: {res.name}")
            print(f"  License: {res.license}")
            print(f"  Duration: {res.duration_sec}s")
            
        if results:
            first_sound = results[0]
            preview_avail = "YES" if first_sound.preview_url else "NO"
            print(f"preview URL available: {preview_avail}")
            
            if first_sound.preview_url:
                tmp_path = f"/tmp/diagnose_sfx_{first_sound.external_id}.mp3"
                print(f"Downloading preview to: {tmp_path}...")
                downloaded = provider.download(first_sound, tmp_path)
                
                if os.path.exists(downloaded.local_path) and os.path.getsize(downloaded.local_path) > 0:
                    print("preview download: PASSED")
                    print(f"Downloaded file size: {os.path.getsize(downloaded.local_path)} bytes")
                    print("FREESOUND_LIVE_SMOKE_PASSED")
                    sys.exit(0)
                else:
                    print("preview download: FAILED (Empty file or not found)")
                    print("FREESOUND_LIVE_SMOKE_FAILED")
                    sys.exit(1)
            else:
                print("Error: No preview URL found in top result", file=sys.stderr)
                print("FREESOUND_LIVE_SMOKE_FAILED")
                sys.exit(1)
        else:
            print("Error: Zero search results returned", file=sys.stderr)
            print("FREESOUND_LIVE_SMOKE_FAILED")
            sys.exit(1)

    except Exception as e:
        print("HTTP request succeeded: NO")
        print(f"Request Error: {e}", file=sys.stderr)
        print("FREESOUND_LIVE_SMOKE_FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
