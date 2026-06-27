from __future__ import annotations

import argparse
import json
import os

from hindsight_local.agent.memory_agent import HindsightMemoryAgent
from hindsight_local.storage.sqlite_store import SQLiteMemoryStore
from hindsight_local.sync.bundles import export_sync_bundle, import_sync_bundle


def get_db_path(cli_db: str | None = None) -> str:
    """Get database path with precedence: CLI arg > ENV var > default."""
    if cli_db is not None:
        return cli_db
    env_db = os.environ.get("HINDSIGHT_DB")
    if env_db:
        return env_db
    return "agent-mem.db"


def main() -> None:
    parser = argparse.ArgumentParser(prog="agent-mem")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--db", default=None)

    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("--db", default=None)
    p_ingest.add_argument("--text", required=True)
    p_ingest.add_argument("--source-uri", default="cli:text")
    p_ingest.add_argument("--title")

    p_search = sub.add_parser("search")
    p_search.add_argument("--db", default=None)
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--limit", type=int, default=5)

    p_export = sub.add_parser("export-sync")
    p_export.add_argument("--db", default=None)
    p_export.add_argument("--out", required=True)

    p_import = sub.add_parser("import-sync")
    p_import.add_argument("--db", default=None)
    p_import.add_argument("--infile", required=True)

    args = parser.parse_args()

    if args.cmd == "init":
        db_path = get_db_path(args.db)
        SQLiteMemoryStore(db_path).init()
        print(json.dumps({"ok": True, "db": db_path}))
    elif args.cmd == "ingest":
        db_path = get_db_path(args.db)
        agent = HindsightMemoryAgent(db_path)
        print(json.dumps(agent.remember(args.text, args.source_uri, args.title), indent=2))
    elif args.cmd == "search":
        db_path = get_db_path(args.db)
        agent = HindsightMemoryAgent(db_path)
        print(json.dumps(agent.recall(args.query, args.limit), indent=2))
    elif args.cmd == "export-sync":
        db_path = get_db_path(args.db)
        store = SQLiteMemoryStore(db_path)
        print(json.dumps({"out": str(export_sync_bundle(store, args.out))}))
    elif args.cmd == "import-sync":
        db_path = get_db_path(args.db)
        store = SQLiteMemoryStore(db_path)
        store.init()
        print(json.dumps({"imported": import_sync_bundle(store, args.infile)}))


if __name__ == "__main__":
    main()
