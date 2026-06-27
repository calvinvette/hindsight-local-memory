from __future__ import annotations

import argparse
import json

from hindsight_local.agent.memory_agent import HindsightMemoryAgent
from hindsight_local.storage.vector_store import HashingEmbedder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild the vector fallback table from existing documents.")
    parser.add_argument("--db", default=".hindsight/agent-mem.db", help="Path to the SQLite database")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    agent = HindsightMemoryAgent(args.db, enable_vector=True)
    if agent.vec_adapter is None:
        raise RuntimeError("Vector support is not enabled")

    embedder = HashingEmbedder()
    with agent.store.connect() as conn:
        agent.vec_adapter.ensure_vector_table(conn)
        conn.execute("DELETE FROM embeddings_fallback")
        conn.commit()

        rows = conn.execute(
            "SELECT doc_id FROM documents ORDER BY created_at"
        ).fetchall()
        for row in rows:
            doc_id = row["doc_id"]
            chunk_rows = conn.execute(
                "SELECT text FROM chunks WHERE doc_id = ? ORDER BY chunk_index",
                (doc_id,),
            ).fetchall()
            text = "\n\n".join(r["text"] for r in chunk_rows)
            embedding = embedder.embed(text or doc_id)
            agent.vec_adapter.upsert_embedding_fallback(conn, doc_id, doc_id, embedding)

    print(json.dumps({"status": "ok", "rows": len(rows)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
