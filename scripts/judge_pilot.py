#!/usr/bin/env python3
"""Prepare, run and summarize a frozen Gemini or local Ollama judge pilot.

Standard library only. Preparing and summarizing never call an API.
Actual calls occur only under `run`; missing/invalid judgments are never failures.
"""
import argparse
import hashlib
import json
import os
import random
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import ollama_backend

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data/pilot/1172_matched_responses.json"
TEMPLATE = ROOT / "data/apex-harness-reference/prompt/grading_prompt.txt"
RESULT_SCHEMA = {"type": "object", "properties": {
    "result": {"type": "integer", "enum": [0, 1]}, "reason": {"type": "string"}},
    "required": ["result", "reason"]}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def prepare(args):
    provider = getattr(args, "provider", "gemini")
    if provider not in {"gemini", "ollama"}:
        raise ValueError("Unsupported provider")
    directory = Path(args.output)
    if (directory / "manifest.json").exists() or (directory / "requests.jsonl").exists():
        raise ValueError("Run directory already has a plan; choose another directory")
    model_pattern = r"[a-zA-Z0-9._:/-]+" if provider == "ollama" else r"[a-zA-Z0-9._-]+"
    if args.repeats < 2 or not re.fullmatch(model_pattern, args.model):
        raise ValueError("Use at least two repeats and a valid model ID")
    if args.max_output_tokens < 1:
        raise ValueError("Maximum output tokens must be positive")
    if provider == "gemini" and (args.thinking_budget < 0 or args.max_output_tokens <= args.thinking_budget):
        raise ValueError("Set 0 <= thinking budget < maximum output tokens")
    if provider == "ollama":
        if args.model.endswith((":cloud", "-cloud")):
            raise ValueError("Select a local Ollama model, not a cloud tag")
        base_url = ollama_backend.local_url(getattr(args, "base_url", "http://127.0.0.1:11434"))
        if getattr(args, "context_window", 4096) < args.max_output_tokens + 1024:
            raise ValueError("Context window must leave at least 1024 tokens beyond the output limit")
    fixture_bytes, template_bytes = FIXTURE.read_bytes(), TEMPLATE.read_bytes()
    fixture = json.loads(fixture_bytes)
    template = template_bytes.decode()
    records = []
    for case in fixture["cases"]:
        for criterion_name, criterion in fixture["original_rubric"].items():
            cid = criterion_name.split()[-1]
            prompt = template.format(criterion_description=criterion["description"], solution=case["response"])
            for repeat in range(args.repeats):
                records.append({
                    "request_id": f"{case['pair_id']}:{case['language']}:c{cid}:r{repeat}",
                    "task_id": fixture["task_id"], "pair_id": case["pair_id"],
                    "language": case["language"], "criterion_id": int(cid), "repeat": repeat,
                    "expected_from_design": case["expected_labels_from_fixture_design"][cid],
                    "prompt": prompt, "prompt_sha256": sha(prompt.encode()),
                })
    random.Random(args.seed).shuffle(records)
    payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records).encode()
    manifest = {
        "schema_version": 2, "created_utc": now(), "provider": provider,
        "model": args.model, "repeats": args.repeats, "shuffle_seed": args.seed,
        "temperature": 0.01, "max_output_tokens": args.max_output_tokens,
        "thinking_budget": args.thinking_budget if provider == "gemini" else None,
        "context": "Pinned public example: criterion description and response only; English grading prompt.",
        "study_status": "exploratory_unreviewed_stimuli", "task_families": 1,
        "human_review_status": "pending", "expected_labels_status": "stimulus_design_not_expert_gold",
        "fixture_sha256": sha(fixture_bytes), "template_sha256": sha(template_bytes),
        "requests_sha256": sha(payload), "planned_calls": len(records),
        "limitation": "Not a reproduction of the production leaderboard; no population-level inference.",
    }
    if provider == "ollama":
        manifest.update({"base_url": base_url, "thinking": getattr(args, "thinking", False),
                         "context_window": getattr(args, "context_window", 4096),
                         "top_p": 0.95, "top_k": 20})
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "requests.jsonl").write_bytes(payload)
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Prepared {len(records)} calls for {args.model}; no API calls made. Expert review pending.")


def load_run(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    payload = (directory / "requests.jsonl").read_bytes()
    if sha(payload) != manifest["requests_sha256"]:
        raise ValueError("Frozen request plan changed")
    plan = [json.loads(line) for line in payload.decode().splitlines()]
    ids = [r["request_id"] for r in plan]
    if len(set(ids)) != len(ids) or len(plan) != manifest["planned_calls"]:
        raise ValueError("Invalid request count or duplicate IDs")
    return manifest, plan


def load_events(directory):
    path = Path(directory) / "results.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def successes(events):
    found = {}
    for event in events:
        if event["status"] == "ok":
            if event["request_id"] in found:
                raise ValueError("Duplicate successful request: do not combine overlapping runs")
            if type(event.get("result")) is not int or event["result"] not in (0, 1):
                raise ValueError("Invalid successful result")
            found[event["request_id"]] = event
    return found


def get_key():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key
    path = ROOT / ".env.local"
    if path.exists():
        for line in path.read_text().splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() in {"GEMINI_API_KEY", "GOOGLE_API_KEY"}:
                value = value.strip().strip('"').strip("'")
                if value:
                    return value
    raise ValueError("Configure GEMINI_API_KEY in the environment or .env.local. Never paste it in chat.")


def parse_response(response):
    candidates = response.get("candidates", [])
    if len(candidates) != 1 or candidates[0].get("finishReason") != "STOP":
        raise ValueError("Missing or incomplete candidate")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    return validate_result(json.loads(text))


def validate_result(parsed):
    if not isinstance(parsed, dict) or type(parsed.get("result")) is not int or parsed["result"] not in (0, 1):
        raise ValueError("Expected an integer result of 0 or 1")
    if not isinstance(parsed.get("reason"), str) or not parsed["reason"].strip():
        raise ValueError("Missing reason")
    return parsed


def request_body(prompt, manifest):
    if manifest["provider"] == "ollama":
        return ollama_backend.payload(prompt, manifest, RESULT_SCHEMA)
    return {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": manifest["temperature"], "candidateCount": 1,
            "maxOutputTokens": manifest["max_output_tokens"],
            "thinkingConfig": {"thinkingBudget": manifest["thinking_budget"]},
            "responseMimeType": "application/json",
            "responseJsonSchema": RESULT_SCHEMA,
        },
    }


def run(args):
    if args.max_calls < 1 or args.delay < 0:
        raise ValueError("max-calls must be positive and delay nonnegative")
    directory = Path(args.output)
    manifest, plan = load_run(directory)
    done = successes(load_events(directory))
    if len(done) == len(plan):
        print("All planned calls already completed; no new calls made.")
        return
    if manifest["provider"] == "gemini":
        headers = {"Content-Type": "application/json", "x-goog-api-key": get_key()}
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{manifest['model']}:generateContent"
    elif manifest["provider"] == "ollama":
        headers = {"Content-Type": "application/json"}
        endpoint = ollama_backend.local_url(manifest["base_url"]) + "/api/chat"
    else:
        raise ValueError("Unsupported provider in plan")
    lock = directory / ".running"
    try:
        lock_stream = lock.open("x")
    except FileExistsError:
        raise ValueError("Another run may be active. Remove .running only after confirming it has stopped.") from None
    calls = 0
    try:
        lock_stream.write(str(os.getpid())); lock_stream.close()
        done = successes(load_events(directory))
        fingerprint_path = directory / "runtime_identity.json"
        if manifest["provider"] == "ollama":
            runtime = ollama_backend.identity(manifest)
            runtime["configuration_sha256"] = sha(json.dumps(manifest, sort_keys=True).encode())
            if fingerprint_path.exists():
                if json.loads(fingerprint_path.read_text()) != runtime:
                    raise ValueError("Ollama server/model identity changed; create a new run directory")
            else:
                fingerprint_path.write_text(json.dumps(runtime, indent=2) + "\n")
        else:
            runtime = None
        for row in plan:
            if row["request_id"] in done:
                continue
            if calls >= args.max_calls:
                break
            body = request_body(row["prompt"], manifest)
            req = Request(endpoint, data=json.dumps(body).encode(), method="POST",
                          headers=headers)
            event = {"request_id": row["request_id"], "started_utc": now(), "status": "error",
                     "model_requested": manifest["model"], "plan_sha256": manifest["requests_sha256"],
                     "configuration_sha256": sha(json.dumps(manifest, sort_keys=True).encode())}
            started = time.monotonic(); fatal = False; calls += 1
            try:
                with urlopen(req, timeout=getattr(args, "timeout", 60)) as stream:
                    response = json.load(stream)
                event["response"] = response
                if manifest["provider"] == "ollama":
                    event["usage"] = {k: response.get(k) for k in ["prompt_eval_count", "eval_count", "total_duration", "load_duration", "prompt_eval_duration", "eval_duration"]}
                    event["model_version"] = runtime["model_digest"]
                    event["runtime_identity"] = runtime
                    event.update(ollama_backend.parse(response, validate_result))
                else:
                    event["usage"] = response.get("usageMetadata", {})
                    event["model_version"] = response.get("modelVersion")
                    event.update(parse_response(response))
                event["status"] = "ok"
            except HTTPError as exc:
                event["error"] = f"HTTP {exc.code}"
                # Do not record server error bodies that could reflect credentials.
                fatal = True
            except (URLError, TimeoutError):
                event["error"] = "Network or timeout error"
                fatal = True
            except (ValueError, KeyError, TypeError):
                event["error"] = "Invalid, blocked or incomplete provider output"
            event["duration_seconds"] = time.monotonic() - started
            with (directory / "results.jsonl").open("a") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n"); stream.flush()
            print(f"{calls}/{args.max_calls} {row['request_id']} {event['status']}", flush=True)
            if fatal:
                print("Stopped after API/network error. Saved progress; rerun to retry unresolved calls.")
                break
            if args.delay and calls < args.max_calls:
                time.sleep(args.delay)
    finally:
        lock.unlink(missing_ok=True)
    print(f"Made {calls} API calls. Results are exploratory; expert review remains pending.")


def summarize(directory):
    manifest, plan = load_run(directory)
    events = load_events(directory)
    by_id = {r["request_id"]: r for r in plan}
    for event in events:
        if event["request_id"] not in by_id or event.get("plan_sha256") != manifest["requests_sha256"]:
            raise ValueError("Results do not match the frozen plan")
        if event.get("configuration_sha256") and event["configuration_sha256"] != sha(json.dumps(manifest, sort_keys=True).encode()):
            raise ValueError("Generation configuration changed after results were collected")
    completed = successes(events)
    groups = defaultdict(list)
    for row in plan:
        groups[(row["pair_id"], row["criterion_id"], row["language"])].append(row)
    cells = []
    for (pair, cid, language), rows in sorted(groups.items()):
        labels = [completed[r["request_id"]]["result"] for r in rows if r["request_id"] in completed]
        cells.append({"pair_id": pair, "criterion_id": cid, "language": language,
                      "planned": len(rows), "valid": len(labels), "passes": sum(labels),
                      "pass_fraction": sum(labels) / len(labels) if labels else None,
                      "expected_from_design": rows[0]["expected_from_design"]})
    lookup = {(c["pair_id"], c["criterion_id"], c["language"]): c for c in cells}
    contrasts = []
    for pair, cid in sorted({(c["pair_id"], c["criterion_id"]) for c in cells}):
        en, es = lookup[(pair, cid, "en")], lookup[(pair, cid, "es")]
        if en["valid"] == en["planned"] and es["valid"] == es["planned"]:
            p, q, n = en["passes"], es["passes"], en["valid"]
            contrasts.append({"pair_id": pair, "criterion_id": cid,
                              "es_minus_en": (q - p) / n,
                              "cross_language_disagreement_all_repeat_pairs": (p * (n-q) + (n-p) * q) / n**2,
                              "within_en_disagreement": 2 * p * (n-p) / (n * (n-1)),
                              "within_es_disagreement": 2 * q * (n-q) / (n * (n-1))})
    task_count = len({r["task_id"] for r in plan})
    output = {"model": manifest["model"], "manifest": manifest, "planned": len(plan),
              "source_tasks": task_count,
              "valid": len(completed), "unresolved": len(plan)-len(completed),
              "failed_attempts": sum(e["status"] != "ok" for e in events),
              "model_versions_observed": sorted({e["model_version"] for e in events if e.get("model_version")}),
              "cells": cells, "complete_cell_contrasts": contrasts,
              "interpretation": f"{task_count} selected source task(s); descriptive only; references are stimulus-design labels, not expert gold."}
    (Path(directory) / "summary.json").write_text(json.dumps(output, indent=2) + "\n")
    print(f"Valid {len(completed)}/{len(plan)}; errors are missing, never criterion failures.")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--provider", choices=["gemini", "ollama"], default="gemini")
    prep.add_argument("--model", default=None)
    prep.add_argument("--repeats", type=int, default=3)
    prep.add_argument("--seed", type=int, default=20260912)
    prep.add_argument("--thinking-budget", type=int, default=1024)
    prep.add_argument("--max-output-tokens", type=int, default=None)
    prep.add_argument("--base-url", default="http://127.0.0.1:11434")
    prep.add_argument("--context-window", type=int, default=4096)
    prep.add_argument("--thinking", action="store_true", help="Enable extended thinking for local Ollama models")
    prep.add_argument("--output", default=None)
    execute = sub.add_parser("run")
    execute.add_argument("--output", default="runs/1172-flash")
    execute.add_argument("--max-calls", type=int, default=12, help="Maximum attempts in this invocation, not a monetary budget")
    execute.add_argument("--delay", type=float, default=1.0)
    execute.add_argument("--timeout", type=float, default=60, help="Per-call network timeout in seconds")
    summary = sub.add_parser("summarize")
    summary.add_argument("--output", default="runs/1172-flash")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            args.model = args.model or ("qwen3:1.7b" if args.provider == "ollama" else "gemini-2.5-flash")
            args.output = args.output or ("runs/1172-qwen3-1.7b" if args.provider == "ollama" else "runs/1172-flash")
            args.max_output_tokens = args.max_output_tokens or (512 if args.provider == "ollama" else 2048)
            prepare(args)
        elif args.command == "run": run(args)
        else: summarize(args.output)
    except (URLError, TimeoutError):
        parser.exit(1, "Cannot reach the provider. For Qwen, start Ollama and check the local endpoint.\n")
    except (ValueError, FileNotFoundError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
