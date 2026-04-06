#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path.home() / ".local" / "share" / "build-club-applications"
DEFAULT_DB_PATH = DATA_DIR / "candidates.json"
DEFAULT_REPORT_PATH = DATA_DIR / "latest_report.md"
SCHEMA_VERSION = 1


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "candidate"


def clamp_score(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        numeric = round(float(value))
    except (TypeError, ValueError):
        return None
    return max(1, min(10, int(numeric)))


def deep_merge(base: object, incoming: object) -> object:
    if isinstance(base, dict) and isinstance(incoming, dict):
        merged = {key: deepcopy(value) for key, value in base.items()}
        for key, value in incoming.items():
            if key in merged:
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged
    if incoming is None:
        return deepcopy(base)
    return deepcopy(incoming)


def load_db(path: Path) -> dict:
    if not path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now(),
            "candidates": [],
        }

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit(f"Expected object at root of {path}")

    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("updated_at", utc_now())
    data.setdefault("candidates", [])

    if not isinstance(data["candidates"], list):
        raise SystemExit(f"`candidates` must be a list in {path}")

    return data


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def read_input(path: str | None) -> object:
    if path:
        raw = Path(path).read_text()
    else:
        raw = sys.stdin.read()

    if not raw.strip():
        raise SystemExit("No input JSON provided.")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Failed to parse input JSON: {exc}") from exc


def normalize_candidate(record: dict) -> dict:
    profile = record.get("profile") or {}
    application = record.get("application") or {}
    scoring = record.get("scoring") or {}
    workflow = record.get("workflow") or {}
    extracted = record.get("extracted") or {}
    responses = record.get("responses") or {}

    name = profile.get("name") or record.get("name") or "Unknown Candidate"
    message_id = (
        application.get("gmail_message_id")
        or application.get("message_id")
        or record.get("gmail_message_id")
        or record.get("message_id")
    )
    candidate_id = record.get("candidate_id")
    if not candidate_id:
        suffix = slugify((message_id or "manual")[-8:])
        candidate_id = f"{slugify(name)}-{suffix}"

    normalized = {
        "candidate_id": candidate_id,
        "profile": {
            "name": name,
            "whatsapp": profile.get("whatsapp"),
            "location": profile.get("location"),
            "link": profile.get("link"),
        },
        "application": {
            "gmail_message_id": message_id,
            "subject": application.get("subject"),
            "received_at": application.get("received_at"),
            "gmail_url": application.get("gmail_url"),
            "source": application.get("source") or "gmail/build-club",
        },
        "responses": {
            "current_work": responses.get("current_work"),
            "accomplishment": responses.get("accomplishment"),
        },
        "extracted": {
            "skills": extracted.get("skills") or [],
            "motivation_signals": extracted.get("motivation_signals") or [],
            "ecom_signals": extracted.get("ecom_signals") or [],
            "ai_padding_signals": extracted.get("ai_padding_signals") or [],
        },
        "scoring": {
            "overall": clamp_score(scoring.get("overall")),
            "motivation": clamp_score(scoring.get("motivation")),
            "skill_fit": clamp_score(scoring.get("skill_fit")),
            "ecom_fit": clamp_score(scoring.get("ecom_fit")),
            "application_quality": clamp_score(scoring.get("application_quality")),
            "authenticity": clamp_score(scoring.get("authenticity")),
            "rationale": scoring.get("rationale"),
            "evidence": scoring.get("evidence") or [],
        },
        "workflow": {
            "status": workflow.get("status") or "new",
            "reviewer_notes": workflow.get("reviewer_notes"),
            "manual_tags": workflow.get("manual_tags") or [],
        },
        "updated_at": utc_now(),
    }

    if record.get("created_at"):
        normalized["created_at"] = record["created_at"]

    return normalized


def merge_candidate(existing: dict | None, incoming: dict) -> dict:
    normalized = normalize_candidate(incoming)
    if not existing:
        normalized["created_at"] = utc_now()
        return normalized

    merged = deep_merge(existing, normalized)
    merged["candidate_id"] = existing.get("candidate_id") or normalized["candidate_id"]
    merged["created_at"] = existing.get("created_at") or normalized.get("created_at") or utc_now()
    merged["updated_at"] = utc_now()
    return merged


def build_index(candidates: list[dict]) -> dict[str, dict]:
    index = {}
    for candidate in candidates:
        candidate_id = candidate.get("candidate_id")
        message_id = candidate.get("application", {}).get("gmail_message_id")
        if candidate_id:
            index[candidate_id] = candidate
        if message_id:
            index[message_id] = candidate
    return index


def sort_candidates(candidates: list[dict]) -> list[dict]:
    def sort_key(candidate: dict) -> tuple:
        overall = candidate.get("scoring", {}).get("overall")
        received_at = candidate.get("application", {}).get("received_at") or ""
        name = candidate.get("profile", {}).get("name") or ""
        return (
            -(overall if isinstance(overall, int) else -1),
            received_at,
            name.lower(),
        )

    return sorted(candidates, key=sort_key, reverse=False)


def render_report(db: dict, limit: int = 25) -> str:
    candidates = sort_candidates(db.get("candidates", []))
    lines = [
        "# Build Club Applications",
        "",
        f"Updated: {db.get('updated_at', utc_now())}",
        f"Candidates: {len(candidates)}",
        "",
    ]

    if not candidates:
        lines.append("No candidates saved yet.")
        lines.append("")
        return "\n".join(lines)

    lines.append("## Ranked Candidates")
    lines.append("")
    for index, candidate in enumerate(candidates[:limit], start=1):
        name = candidate.get("profile", {}).get("name") or "Unknown Candidate"
        location = candidate.get("profile", {}).get("location") or "Unknown"
        status = candidate.get("workflow", {}).get("status") or "new"
        score = candidate.get("scoring", {}).get("overall")
        rationale = candidate.get("scoring", {}).get("rationale") or "No rationale saved."
        link = candidate.get("profile", {}).get("link")
        lines.append(
            f"{index}. {name} | score {score if score is not None else '?':>2}/10 | {location} | {status}"
        )
        lines.append(f"   {rationale}")
        if link:
            lines.append(f"   Link: {link}")
        evidence = candidate.get("scoring", {}).get("evidence") or []
        for item in evidence[:2]:
            lines.append(f"   - {item}")
        lines.append("")

    return "\n".join(lines)


def upsert_records(db_path: Path, report_path: Path, input_path: str | None) -> None:
    payload = read_input(input_path)
    if isinstance(payload, dict):
        records = payload.get("candidates") if "candidates" in payload else [payload]
    elif isinstance(payload, list):
        records = payload
    else:
        raise SystemExit("Input JSON must be an object or array.")

    if not all(isinstance(item, dict) for item in records):
        raise SystemExit("Each candidate record must be a JSON object.")

    db = load_db(db_path)
    index = build_index(db["candidates"])
    merged_candidates = list(db["candidates"])
    added = 0
    updated = 0

    for record in records:
        normalized = normalize_candidate(record)
        message_id = normalized["application"].get("gmail_message_id")
        existing = index.get(normalized["candidate_id"]) or (index.get(message_id) if message_id else None)
        merged = merge_candidate(existing, normalized)

        if existing:
            position = merged_candidates.index(existing)
            merged_candidates[position] = merged
            updated += 1
        else:
            merged_candidates.append(merged)
            added += 1

        index[merged["candidate_id"]] = merged
        if message_id:
            index[message_id] = merged

    db["candidates"] = sort_candidates(merged_candidates)
    db["updated_at"] = utc_now()
    write_json(db_path, db)
    report_path.write_text(render_report(db) + "\n")

    print(f"Saved {len(records)} candidate record(s). Added {added}, updated {updated}.")
    print(f"DB: {db_path}")
    print(f"Report: {report_path}")


def report_records(db_path: Path, report_path: Path, limit: int) -> None:
    db = load_db(db_path)
    db["updated_at"] = utc_now()
    report = render_report(db, limit=limit)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report + "\n")
    print(report)


def db_stats(db_path: Path, as_json: bool) -> None:
    db = load_db(db_path)
    candidates = db.get("candidates", [])
    message_ids = [
        candidate.get("application", {}).get("gmail_message_id")
        for candidate in candidates
        if candidate.get("application", {}).get("gmail_message_id")
    ]
    received_values = [
        candidate.get("application", {}).get("received_at")
        for candidate in candidates
        if candidate.get("application", {}).get("received_at")
    ]
    scored_count = sum(
        1
        for candidate in candidates
        if candidate.get("scoring", {}).get("overall") is not None
    )
    payload = {
        "candidate_count": len(candidates),
        "scored_count": scored_count,
        "known_message_ids_count": len(message_ids),
        "latest_received_at": max(received_values) if received_values else None,
        "updated_at": db.get("updated_at"),
    }
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    for key, value in payload.items():
        print(f"{key}: {value}")


def list_message_ids(db_path: Path) -> None:
    db = load_db(db_path)
    ids = sorted(
        {
            candidate.get("application", {}).get("gmail_message_id")
            for candidate in db.get("candidates", [])
            if candidate.get("application", {}).get("gmail_message_id")
        }
    )
    for item in ids:
        print(item)


def find_candidate(db: dict, identifier: str) -> dict:
    lowered = identifier.strip().lower()
    for candidate in db.get("candidates", []):
        candidate_id = (candidate.get("candidate_id") or "").lower()
        message_id = (candidate.get("application", {}).get("gmail_message_id") or "").lower()
        name = (candidate.get("profile", {}).get("name") or "").lower()
        if lowered in {candidate_id, message_id, name}:
            return candidate
    raise SystemExit(f"Candidate not found: {identifier}")


def set_status(db_path: Path, report_path: Path, identifier: str, status: str, notes: str | None) -> None:
    db = load_db(db_path)
    candidate = find_candidate(db, identifier)
    candidate.setdefault("workflow", {})
    candidate["workflow"]["status"] = status
    if notes is not None:
        candidate["workflow"]["reviewer_notes"] = notes
    candidate["updated_at"] = utc_now()
    db["updated_at"] = utc_now()
    db["candidates"] = sort_candidates(db["candidates"])
    write_json(db_path, db)
    report_path.write_text(render_report(db) + "\n")
    print(f"Updated {candidate.get('candidate_id')} to status `{status}`.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the Build Club application tracker.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to candidates JSON DB.")
    parser.add_argument(
        "--report",
        default=str(DEFAULT_REPORT_PATH),
        help="Path to markdown report output.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    upsert = subparsers.add_parser("upsert", help="Upsert candidate records from JSON.")
    upsert.add_argument("--input", help="Optional JSON file path. Defaults to stdin.")

    report = subparsers.add_parser("report", help="Render the markdown report.")
    report.add_argument("--limit", type=int, default=25, help="Maximum candidates to include.")

    stats = subparsers.add_parser("stats", help="Show DB stats for incremental syncs.")
    stats.add_argument("--json", action="store_true", help="Print stats as JSON.")

    subparsers.add_parser("list-message-ids", help="Print known Gmail message IDs, one per line.")

    set_status_parser = subparsers.add_parser("set-status", help="Set a candidate workflow status.")
    set_status_parser.add_argument("--id", required=True, help="candidate_id, Gmail message id, or exact name.")
    set_status_parser.add_argument("--status", required=True, help="New workflow status.")
    set_status_parser.add_argument("--notes", help="Optional reviewer note.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    db_path = Path(args.db)
    report_path = Path(args.report)

    if args.command == "upsert":
        upsert_records(db_path, report_path, args.input)
    elif args.command == "report":
        report_records(db_path, report_path, args.limit)
    elif args.command == "stats":
        db_stats(db_path, args.json)
    elif args.command == "list-message-ids":
        list_message_ids(db_path)
    elif args.command == "set-status":
        set_status(db_path, report_path, args.id, args.status, args.notes)
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
