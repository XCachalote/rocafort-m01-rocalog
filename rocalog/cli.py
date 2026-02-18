"""Command-line interface for RocaLog."""

from __future__ import annotations

import argparse
import json

from .parser import parse_failed_passwords, summarize_attempts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse auth.log failed password attempts")
    parser.add_argument("--file", required=True, help="Path to auth.log file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    with open(args.file, "r", encoding="utf-8") as file:
        log_text = file.read()

    attempts = parse_failed_passwords(log_text)
    summary = summarize_attempts(attempts)

    output = {"attempts": attempts, "summary": summary}

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"Total failed attempts: {len(attempts)}")
        print("Top IPs:")
        for item in summary["top_ips"]:
            print(f"  {item['ip']}: {item['count']}")
        print("Top users:")
        for item in summary["top_users"]:
            print(f"  {item['user']}: {item['count']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
