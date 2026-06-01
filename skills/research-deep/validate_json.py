#!/usr/bin/env python3
"""Validate that research JSON output covers all fields from fields.yaml."""
import sys, json, argparse
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip install pyyaml")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--fields", required=True, help="fields.yaml file")
    parser.add_argument("-j", "--json", required=True, help="research output JSON file")
    args = parser.parse_args()

    with open(args.fields) as f:
        fields_def = yaml.safe_load(f)
    with open(args.json) as f:
        data = json.load(f)

    expected = {f["name"] for f in fields_def.get("fields", [])}
    actual = set(data.get("fields", {}).keys())

    missing = expected - actual
    extra = actual - expected

    if missing:
        print(f"WARNING: Missing fields: {', '.join(sorted(missing))}")
    if extra:
        print(f"INFO: Extra fields (not in schema): {', '.join(sorted(extra))}")

    uncertain = data.get("uncertain", [])
    if uncertain:
        print(f"INFO: Uncertain fields: {', '.join(uncertain)}")

    if not missing:
        print("VALIDATION PASSED: All fields covered.")
        return 0
    else:
        print(f"VALIDATION FAILED: {len(missing)} fields missing.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
