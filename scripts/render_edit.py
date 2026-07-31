import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from agents.editing.orchestrator import EditOrchestrator


def main():
    parser = argparse.ArgumentParser(description="Render an edited content item.")
    parser.add_argument("custom_id", help="Content custom_id, e.g. ELN-RAW-...")
    parser.add_argument("--hook", default=None, help="Optional hook text overlay")
    parser.add_argument("--actor", default="cli-editor", help="Actor name for audit log")
    args = parser.parse_args()

    orchestrator = EditOrchestrator()
    result = orchestrator.render_content(args.custom_id, hook_text=args.hook, actor=args.actor)
    if result.get("ok"):
        print(f"OK: {result['custom_id']} -> {result['output_key']}")
        return 0
    print(f"FAILED: {result.get('error')}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
