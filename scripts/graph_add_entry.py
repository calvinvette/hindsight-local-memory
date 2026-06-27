from __future__ import annotations

import argparse
import json

from hindsight_local.agent.memory_agent import HindsightMemoryAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project a document or edge into FalkorDB.")
    parser.add_argument("--db", default=".hindsight/agent-mem.db", help="Path to the SQLite database")
    parser.add_argument("--kind", choices=("document", "edge"), required=True)
    parser.add_argument("--doc-id", default=None, help="Document ID for document projection")
    parser.add_argument("--title", default=None, help="Title for document projection")
    parser.add_argument("--metadata", default="{}", help="JSON metadata for document projection")
    parser.add_argument("--source-id", default=None, help="Source ID for edge projection")
    parser.add_argument("--relation", default=None, help="Relation name for edge projection")
    parser.add_argument("--target-id", default=None, help="Target ID for edge projection")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    agent = HindsightMemoryAgent(args.db, enable_falkordb=True)
    if args.kind == "document":
        if not args.doc_id:
            raise SystemExit("--doc-id is required for document projection")
        metadata = json.loads(args.metadata) if args.metadata else {}
        agent.project_document(args.doc_id, title=args.title, metadata=metadata)
        print(json.dumps({"kind": "document", "doc_id": args.doc_id, "title": args.title}, indent=2, sort_keys=True))
        return

    if not all([args.source_id, args.relation, args.target_id]):
        raise SystemExit("--source-id, --relation, and --target-id are required for edge projection")
    agent.project_edge(args.source_id, args.relation, args.target_id)
    print(
        json.dumps(
            {"kind": "edge", "source_id": args.source_id, "relation": args.relation, "target_id": args.target_id},
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
