#!/usr/bin/env python
import os
import sys
import argparse
import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agents.audio.freesound_provider import FreesoundProvider, normalize_license

FREESOUND_API_BASE = "https://freesound.org/apiv2"


def main():
    parser = argparse.ArgumentParser(description="Diagnose Freesound API Provider")
    parser.add_argument("--query", default="rain", help="Query search term")
    args = parser.parse_args()

    api_key = os.environ.get("FREESOUND_API_KEY") or os.environ.get("FREESOUND_CLIENT_SECRET")
    if not api_key:
        print("credentials present: NO")
        print("FREESOUND_LIVE_SMOKE_FAILED", file=sys.stderr)
        sys.exit(1)
    else:
        print("credentials present: YES")

    print("\n--- Phase 2: Running Raw Differential Diagnostics ---")
    headers = {"Authorization": f"Token {api_key}"}
    
    variants = [
        ("A. Query only", {"query": args.query, "fields": "id,name,license"}),
        ("B. Query + duration", {"query": args.query, "filter": "duration:[0 TO 15]", "fields": "id,name,license"}),
        ("C. Query + CC0", {"query": args.query, "filter": "duration:[0 TO 15] license:\"Creative Commons 0\"", "fields": "id,name,license"}),
        ("D. Query + Attribution", {"query": args.query, "filter": "duration:[0 TO 15] license:Attribution", "fields": "id,name,license"}),
        ("E. Current combined filter", {"query": args.query, "filter": "duration:[0 TO 15] license:(\"Creative Commons 0\" OR \"Attribution\")", "fields": "id,name,license,previews"})
    ]
    
    for name, params in variants:
        print(f"\nVariant: {name}")
        try:
            res = requests.get(f"{FREESOUND_API_BASE}/search/", params=params, headers=headers, timeout=15)
            print(f"  HTTP status: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                results = data.get("results", [])
                print(f"  API JSON count: {data.get('count')}")
                print(f"  len(raw results): {len(results)}")
                licenses = [r.get("license") for r in results[:3]]
                names = [r.get("name") for r in results[:3]]
                print(f"  first 3 license values: {licenses}")
                print(f"  first 3 sound names: {names}")
                preview_avail = "YES" if any(r.get("previews") for r in results) else "NO"
                print(f"  preview URL present: {preview_avail}")
            else:
                print(f"  Response: {res.text[:200]}")
        except Exception as e:
            print(f"  Error during search: {e}")

    print("\n--- General API Authentication & Response Classification ---")
    try:
        r_unfiltered = requests.get(
            f"{FREESOUND_API_BASE}/search/",
            params={"query": args.query, "fields": "id,name,license"},
            headers=headers,
            timeout=15
        )
        status = r_unfiltered.status_code
        print(f"authenticated HTTP request status: {status}")
        
        if status == 401:
            print("SFX_AUTH_FAILED")
            print("FREESOUND_LIVE_SMOKE_FAILED")
            sys.exit(1)
            
        if status == 200:
            data = r_unfiltered.json()
            raw_count = data.get("count", 0)
            print(f"raw API count: {raw_count}")
            
            provider = FreesoundProvider()
            accepted_results = provider.search(args.query, max_duration_sec=15.0)
            print(f"raw page result count: {len(data.get('results', []))}")
            print(f"accepted commercial-safe results: {len(accepted_results)}")
            
            if raw_count == 0:
                print("SFX_SEARCH_EMPTY_UPSTREAM")
                print("FREESOUND_LIVE_SMOKE_FAILED")
                sys.exit(1)
            elif len(accepted_results) == 0:
                print("SFX_LICENSE_FILTER_EMPTY")
                print("FREESOUND_LIVE_SMOKE_FAILED")
                sys.exit(1)
            else:
                first_sound = accepted_results[0]
                preview_avail = "YES" if first_sound.preview_url else "NO"
                print(f"preview URL available: {preview_avail}")
                
                if first_sound.preview_url:
                    tmp_path = f"/tmp/diagnose_sfx_{first_sound.external_id}.mp3"
                    print(f"Downloading preview to: {tmp_path}...")
                    downloaded = provider.download(first_sound, tmp_path)
                    
                    if os.path.exists(downloaded.local_path) and os.path.getsize(downloaded.local_path) > 0:
                        print("preview download: PASSED")
                        print("FREESOUND_LIVE_SMOKE_PASSED")
                        sys.exit(0)
                    else:
                        print("preview download: FAILED")
                        print("FREESOUND_LIVE_SMOKE_FAILED")
                        sys.exit(1)
                else:
                    print("Error: No preview URL found in top result", file=sys.stderr)
                    print("FREESOUND_LIVE_SMOKE_FAILED")
                    sys.exit(1)
        else:
            print(f"HTTP request failed with status {status}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error during diagnostics: {e}", file=sys.stderr)
        print("FREESOUND_LIVE_SMOKE_FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
