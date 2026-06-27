from __future__ import annotations

import argparse
import json

from hindsight_local.agent.memory_agent import HindsightMemoryAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest text and populate the vector table.")
    parser.add_argument("--db", default=".hindsight/agent-mem.db", help="Path to the SQLite database")
    parser.add_argument("--text", required=True, help="Text to ingest")
    parser.add_argument("--source-uri", default="agent:script", help="Source URI for the document")
    parser.add_argument("--title", default=None, help="Optional title for the document")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    agent = HindsightMemoryAgent(args.db, enable_vector=True)
    result = agent.remember(args.text, source_uri=args.source_uri, title=args.title, embed=True)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
