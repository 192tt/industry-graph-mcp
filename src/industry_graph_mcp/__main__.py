"""CLI entry: setup | mcp | search | fetch | plan."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["mcp"]

    cmd = argv[0]
    rest = argv[1:]

    if cmd in ("mcp", "serve", "server"):
        from industry_graph_mcp.mcp_server import main as mcp_main

        mcp_main()
        return

    if cmd in ("setup", "wizard"):
        sys.argv = ["industry-graph-setup", *rest]
        from industry_graph_mcp.setup_wizard import main as setup_main

        setup_main()
        return

    if cmd in ("search", "fetch", "plan"):
        sys.argv = ["search_fetch", cmd, *rest]
        from industry_graph_mcp.search_fetch import main as sf_main

        sf_main()
        return

    if cmd in ("-h", "--help", "help"):
        print(
            "Usage:\n"
            "  python -m industry_graph_mcp setup [-y] [--backend sqlite|neo4j]\n"
            "  python -m industry_graph_mcp mcp\n"
            "  python -m industry_graph_mcp search \"query\"\n"
            "  python -m industry_graph_mcp fetch URL\n"
            "  python -m industry_graph_mcp plan \"我想调研一下广东的制造业\"\n"
        )
        return

    print(f"Unknown command: {cmd}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
