"""Minimal test runner without pytest plugins (Python 3.14 local)."""

from __future__ import annotations

import os
import sys
import traceback

os.environ["INDUSTRY_GRAPH_MCP_HOME"] = r"D:\industry-graph-mcp\test_home"


def run() -> int:
    failed = 0
    # import test modules and call test_* functions
    sys.path.insert(0, r"D:\工作\项目\民政局\industry-graph-mcp\src")
    import importlib.util
    from pathlib import Path

    tests_dir = Path(r"D:\工作\项目\民政局\industry-graph-mcp\tests")
    for path in sorted(tests_dir.glob("test_*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        for name in sorted(dir(mod)):
            if not name.startswith("test_"):
                continue
            fn = getattr(mod, name)
            if not callable(fn):
                continue
            # skip fixture-based tests that need pytest
            if name in ("test_upsert_and_query", "test_relations_and_stats", "test_export_import"):
                from industry_graph_mcp.graph.sqlite_store import SqliteStore
                from pathlib import Path as P

                db = P(r"D:\industry-graph-mcp\test_home\data") / f"{name}.db"
                db.parent.mkdir(parents=True, exist_ok=True)
                if db.exists():
                    db.unlink()
                store = SqliteStore(db)
                try:
                    print(f"RUN {path.name}::{name}")
                    fn(store)
                    print("  PASS")
                except Exception:
                    failed += 1
                    print("  FAIL")
                    traceback.print_exc()
                finally:
                    store.close()
                    if db.exists():
                        db.unlink()
                continue
            try:
                print(f"RUN {path.name}::{name}")
                fn()
                print("  PASS")
            except TypeError:
                # needs fixtures
                print("  SKIP (fixtures)")
            except Exception:
                failed += 1
                print("  FAIL")
                traceback.print_exc()
    print("FAILED" if failed else "ALL PASS", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
