from __future__ import annotations

import argparse
import json

from hindsight_local.agent.memory_agent import HindsightMemoryAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild FalkorDB projections from existing SQLite records.")
    parser.add_argument("--db", default=".hindsight/agent-mem.db", help="Path to the SQLite database")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    agent = HindsightMemoryAgent(args.db, enable_falkordb=True)

    with agent.store.connect() as conn:
        documents = conn.execute(
            "SELECT doc_id, title, metadata_json FROM documents ORDER BY created_at"
        ).fetchall()
        for row in documents:
            metadata = json.loads(row["metadata_json"] or "{}")
            agent.project_document(row["doc_id"], title=row["title"], metadata=metadata)

        edges = conn.execute(
            "SELECT source_id, relation, target_id FROM graph_edges ORDER BY created_at"
        ).fetchall()
        for row in edges:
            agent.project_edge(row["source_id"], row["relation"], row["target_id"])

    print(
        json.dumps(
            {"status": "ok", "documents": len(documents), "edges": len(edges)},
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
