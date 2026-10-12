#!/usr/bin/env python3
"""Ingest one closed Project E batch into an append-only evidence ledger."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from credentialing.ingestion import empty_ledger, ingest_batch, load_ledger


def save_ledger(path: Path, ledger: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            json.dump(ledger, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest a batch export without applying credentialing decisions.")
    parser.add_argument("batch_dir", type=Path, help="directory containing one batch README, CSVs, and indexed documents")
    parser.add_argument("--ledger", type=Path, help="existing evidence ledger to merge into")
    parser.add_argument("--output", type=Path, help="ledger output path (defaults to --ledger, or deliverables/evidence-ledger.json)")
    args = parser.parse_args(argv)

    try:
        current = load_ledger(args.ledger) if args.ledger else empty_ledger()
        result = ingest_batch(args.batch_dir, current)
        output_path = args.output or args.ledger or Path("deliverables/evidence-ledger.json")
        if result.changed:
            save_ledger(output_path, result.ledger)
        elif args.ledger is None and result.batch_id is None:
            # A new run with an unreadable README has nothing safe to serialize.
            pass
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 2

    if result.changed:
        print(f"Ingested {result.batch_id} into {output_path}")
    else:
        print(f"No ledger changes for {result.batch_id or args.batch_dir}")
    for issue in result.issues:
        location = issue.filename or "batch"
        if issue.row_number is not None:
            location += f":{issue.row_number}"
        print(f"{issue.code} [{location}]: {issue.message}", file=sys.stderr)
    return 1 if result.issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
