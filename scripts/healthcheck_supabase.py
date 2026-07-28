import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from agents.db.supabase_client import ElinaDB
from agents.storage.supabase_storage import ElinaStorage


def run_healthcheck() -> None:
    print("Running Supabase healthcheck...")

    db_ok = False
    storage_ok = False

    try:
        db = ElinaDB()
        print("DB client initialized.")
        res = db.client.table("content_items").select("id").limit(1).execute()
        print(f"DB connection OK. Rows fetched: {len(res.data)}")
        db_ok = True
    except Exception as exc:
        print(f"DB ERROR: {exc}")

    try:
        storage = ElinaStorage()
        print("Storage client initialized.")
        files = storage.list_files("")
        print(f"Storage connection OK. Objects visible: {len(files)}")
        storage_ok = True
    except Exception as exc:
        print(f"STORAGE ERROR: {exc}")

    if db_ok and storage_ok:
        print("HEALTHCHECK PASSED")
    else:
        print("HEALTHCHECK FAILED")
        sys.exit(1)


if __name__ == "__main__":
    run_healthcheck()
