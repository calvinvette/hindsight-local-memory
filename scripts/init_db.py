from __future__ import annotations

import argparse
from hindsight_local.storage.sqlite_store import SQLiteMemoryStore

parser = argparse.ArgumentParser()
parser.add_argument("--db", required=True)
args = parser.parse_args()
SQLiteMemoryStore(args.db).init()
print(f"initialized {args.db}")
