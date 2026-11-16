"""Command line for the evaluation: ``python -m ferrero.eval``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..assistant.agent import Assistant, make_client
from ..casemodel import CaseModel
from ..config import get_settings
from ..sync.index import DocumentIndex
from .golden import PROBES, load_golden, run_one, write_report


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="ferrero-eval", description="Score the assistant on the golden set.")
    parser.add_argument("--golden", type=Path, default=settings.golden_set_path, help="golden_set.csv to use")
    parser.add_argument("--ids", help="comma-separated question ids to run (default: all)")
    parser.add_argument("--user", default="U-08", help="user to ask as (default U-08, Legal-Ops, sees everything)")
    parser.add_argument("--no-probes", action="store_true", help="skip the access-control probes")
    parser.add_argument("--judge-model", default=settings.model)
    parser.add_argument("--yes", action="store_true", help="don't ask for confirmation before calling the API")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    rows = load_golden(args.golden)
    if not args.no_probes:
        rows += [dict(p) for p in PROBES]
    if args.ids:
        wanted = {i.strip().upper() for i in args.ids.split(",")}
        rows = [r for r in rows if r["gs_id"].upper() in wanted]
    if not rows:
        print("No questions selected.")
        return 1
    print(f"{len(rows)} questions; each makes a few {settings.model} calls (effort {settings.effort}) plus one "
          f"{args.judge_model} judge call. Usage is billed to your Claude account.")
    if not args.yes and input("Continue? [y/N] ").strip().lower() not in ("y", "yes"):
        return 1

    model = CaseModel(settings.csv_dir, settings.demo_today, catalogue=settings.catalogue_path)
    index = DocumentIndex(settings.index_path, readonly=True)
    if not index.exists:
        print("The document index is missing: run `python -m ferrero.sync` first.")
        return 1
    client = make_client(settings)
    assistant = Assistant(settings, model, index, client=client)
    results = []
    for n, row in enumerate(rows, 1):
        result = run_one(assistant, client, args.judge_model, row, args.user)
        results.append(result)
        status = "PASS" if result.passed else result.verdict.upper()
        print(f"[{n:2d}/{len(rows)}] {result.gs_id:7s} {status:7s} {result.latency_s:5.1f}s  {result.error or ''}")
    meta = {"model": settings.model, "effort": settings.effort, "judge_model": args.judge_model, "user_id": args.user,
            "golden": str(args.golden)}
    json_path, md_path = write_report(results, settings.data_dir / "eval", meta)
    print(f"\n{sum(r.passed for r in results)} of {len(results)} passed. Report: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
