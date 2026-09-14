#!/usr/bin/env python3
"""Download the pinned public development CSV and selected official attachments."""
import argparse
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1] / "data/apex-v1-extended"
REVISION = "e0db9513115f8d0449591fac3d77d4bdc1a98fef"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-ids", nargs="+", default=["1172", "1242", "2108", "2145", "2287"])
    parser.add_argument("--all-attachments", action="store_true", help="Download attachments for all 100 public tasks.")
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
        "dataset": "mercor/APEX-v1-extended", "revision": REVISION, "files": {},
        "access": "Official Hugging Face file downloads; no viewer scraping.",
    }
    if manifest["revision"] != REVISION:
        raise ValueError("Existing manifest has a different revision")

    def fetch(name, local):
        destination = ROOT / local
        recorded = manifest["files"].get(name)
        if destination.exists() and recorded:
            content = destination.read_bytes()
            if hashlib.sha256(content).hexdigest() != recorded["sha256"]:
                raise ValueError(f"Local file changed: {destination}")
            return content
        url = f"https://huggingface.co/datasets/mercor/APEX-v1-extended/resolve/{REVISION}/" + quote(name, safe="/")
        content = urlopen(url, timeout=60).read()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        manifest["files"][name] = {"local_file": local, "url": url, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
        manifest["retrieved_utc"] = datetime.now(timezone.utc).isoformat()
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Downloaded {local}: {len(content):,} bytes")
        return content

    content = fetch("data/train.csv", "train.csv")
    fetch("README.md", "README.md")
    fetch("eval.yaml", "eval.yaml")
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    unknown = set(args.task_ids) - {row["Task ID"] for row in rows}
    if unknown:
        raise ValueError(f"Unknown task IDs: {sorted(unknown)}")
    for row in rows:
        if args.all_attachments or row["Task ID"] in args.task_ids:
            for path in row["File Attachments"].splitlines():
                path = path.strip()
                if not path:
                    continue
                if not path.startswith("documents/") or ".." in Path(path).parts:
                    raise ValueError(f"Unexpected attachment path: {path}")
                fetch(path, path)
    print("Public development data ready. No hidden evaluation data is included.")


if __name__ == "__main__":
    main()
