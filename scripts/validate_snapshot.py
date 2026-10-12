#!/usr/bin/env python3
"""Validate a credentialing batch snapshot against the repository schema."""

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a snapshot JSON file against snapshot.schema.json."
    )
    parser.add_argument("snapshot", type=Path, help="path to the snapshot JSON file")
    args = parser.parse_args()

    schema_path = Path(__file__).resolve().parent.parent / "snapshot.schema.json"
    try:
        with schema_path.open(encoding="utf-8") as schema_file:
            schema = json.load(schema_file)
        with args.snapshot.open(encoding="utf-8") as snapshot_file:
            snapshot = json.load(snapshot_file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        validator = Draft202012Validator(
            schema, format_checker=FormatChecker()
        )
        errors = sorted(validator.iter_errors(snapshot), key=lambda error: list(map(str, error.absolute_path)))
    except SchemaError as exc:
        print(f"Error: invalid schema at {schema_path}: {exc.message}", file=sys.stderr)
        return 1

    if errors:
        print(f"Invalid snapshot: {args.snapshot}", file=sys.stderr)
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "$"
            print(f"  {location}: {error.message}", file=sys.stderr)
        return 1

    print(f"Valid snapshot: {args.snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
