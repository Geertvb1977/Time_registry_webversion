#!/usr/bin/env python3
"""Example: fetch and pretty-print project status using the API token.

Usage:
  python3 scripts/fetch_project_status.py --host https://example.com --token THE_TOKEN --project 123
  python3 scripts/fetch_project_status.py --host https://example.com --token THE_TOKEN --project 123 --header

Install dependency: `pip install requests`
"""

import argparse
import json
import sys

try:
    import requests
except Exception:
    print("Please install requests: pip install requests", file=sys.stderr)
    raise


def fetch(host, token, project_id, use_header=False, timeout=10):
    host = host.rstrip("/")
    url = f"{host}/api/project_status"
    headers = {}
    params = {"project_id": project_id}
    if use_header:
        headers["Authorization"] = f"Token {token}"
    else:
        params["token"] = token

    resp = requests.get(url, headers=headers, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def main():
    p = argparse.ArgumentParser(description="Fetch project status via API token")
    p.add_argument("--host", required=True, help="Base host, e.g. https://example.com")
    p.add_argument("--token", required=True, help="API token")
    p.add_argument("--project", required=True, help="Project id")
    p.add_argument("--header", action="store_true", help="Send token in Authorization header")
    args = p.parse_args()

    try:
        data = fetch(args.host, args.token, args.project, use_header=args.header)
    except requests.HTTPError as e:
        print(f'HTTP error: {e} - {getattr(e.response, "text", "")}', file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
