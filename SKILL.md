---
name: build-club-applications
description: Collect Build Club application emails from Gmail, score applicants for Build Club with a motivation-first rubric, and persist a local JSON tracker plus markdown report. Use when reviewing Build Club applicants, syncing new application emails, updating candidate statuses, or producing a shortlist from Gmail submissions.
---

# Build Club Applications

## Quick Workflow
1. Check the local tracker first:
   `python3 ~/.codex/skills/build-club-applications/scripts/applications_db.py stats --json`
2. Search Gmail with `from:(onboarding@resend.dev) subject:"New application:"`.
3. For incremental runs, add an `after:YYYY/MM/DD` filter based on the latest ranked `received_at`, then dedupe against the existing local DB using:
   `python3 ~/.codex/skills/build-club-applications/scripts/applications_db.py list-message-ids`
4. Batch-read only unseen emails and extract the structured fields.
5. Skip obvious tests and fake submissions. Default skip signals: subject or name contains `test` or `ignore`, or the answers are obvious filler.
6. Score each new candidate from `1` to `10` with the rubric below.
7. Persist the new records with:
   `python3 ~/.codex/skills/build-club-applications/scripts/applications_db.py upsert`
8. Generate or refresh the local report with:
   `python3 ~/.codex/skills/build-club-applications/scripts/applications_db.py report`
9. Export the local private CSV with:
   `python3 ~/.codex/skills/build-club-applications/scripts/applications_db.py export-csv`
10. Export the sanitized public CSV into the public repo with:
   `python3 ~/.codex/skills/build-club-applications/scripts/applications_db.py --csv /home/claude/build-club-applications-skill/data/public_candidate_rankings.csv export-csv --public`
11. If the public CSV changed, commit and push `/home/claude/build-club-applications-skill` so the public repo stays updated after each `check build club` run.

## Incremental Rule
- Do not rescore candidates already present in `/home/claude/.local/share/build-club-applications/candidates.json` unless the user explicitly asks for a re-rank.
- Default behavior on future runs: score only unseen Gmail message IDs.
- If there are no unseen IDs, say that there are no new applications to rank.
- After every `check build club` run, refresh both CSV exports and update the public GitHub repo artifact if it changed.

## Email Parsing Notes
- Newer form variant uses:
  - `What are you working on / how are you using agentic coding tools?`
  - `Most impressive accomplishment:`
- Older form variant uses:
  - `What are you building?`
  - `Most impressive thing you've done?`
- If the Gmail connector returns mojibake like `敎⁷畂汩...`, recover it with:
  `body.encode("utf-16le").decode("utf-8")`
- Keep only the applicant content. Ignore the `Tracking:` block except for source context if it is useful.

## Scoring Rubric
Weight the score in this order:
1. Motivation
2. Skill
3. Authenticity vs AI padding
4. E-com relevance
5. Application quality

Suggested subscores:
- `motivation`: `1-10`
- `skill_fit`: `1-10`
- `ecom_fit`: `1-10`
- `application_quality`: `1-10`
- `authenticity`: `1-10`

Suggested weights:
- `motivation`: `0.40`
- `skill_fit`: `0.20`
- `authenticity`: `0.20`
- `ecom_fit`: `0.10`
- `application_quality`: `0.10`

Scoring rules:
- Favor concrete action, speed, ownership, and evidence of self-direction.
- Do not over-reward polished writing. Substance beats polish.
- Penalize vague buzzword-heavy applications that look padded by AI without concrete proof.
- Give credit when AI usage is practical and outcome-oriented.
- E-com relevance is a boost, not the top criterion. A highly motivated builder with strong execution can still score well without obvious e-com experience.
- Round the weighted result to the nearest integer and clamp to `1-10`.

## Authenticity Filter
- Treat authenticity as a gate, not a cosmetic adjustment.
- If the application reads like AI-generated founder copy instead of a real human explaining what they did, subtract aggressively.
- Common red flags:
  - repeated em dashes and polished marketing cadence
  - too many abstract phrases with too little operational detail
  - long copy that sounds like a landing page, not an application
  - generic startup superlatives without personal specifics
  - obvious founder-theater phrasing like `from idea to live store in minutes, not days`
- Positive signals:
  - awkward but concrete wording
  - admitting constraints, uncertainty, or missing experience
  - specific timelines, customers, failures, commits, revenue, or shipped outputs
  - language that sounds like an operator, not a copywriter

## Hard Caps
- If the application is obvious AI slop with weak personal signal, cap `overall` at `6`, even if the idea is good.
- If the application is both AI-sloppy and low-evidence, cap `overall` at `4`.
- Only allow `9-10` when the applicant combines:
  - very high motivation
  - strong concrete proof of execution
  - high authenticity
- Never give a `10` to a candidate whose written application itself would lower the signal quality of the group chat.

## What To Store
For each candidate, store:
- `candidate_id`
- `profile`: `name`, `whatsapp`, `location`, `link`
- `application`: `gmail_message_id`, `subject`, `received_at`, `gmail_url`, `source`
- `responses`: `current_work`, `accomplishment`
- `extracted`: `skills`, `motivation_signals`, `ecom_signals`, `ai_padding_signals`
- `scoring`: `overall`, all subscores, `rationale`, `evidence`
- `workflow`: `status`, `reviewer_notes`, `manual_tags`

Default `workflow.status` should be one of:
- `new`
- `shortlist`
- `hold`
- `pass`
- `contacted`

## Persistence Commands
Upsert candidates from JSON on stdin:

```bash
python3 ~/.codex/skills/build-club-applications/scripts/applications_db.py upsert <<'JSON'
[
  {
    "profile": {
      "name": "Example Candidate",
      "location": "Hong Kong"
    },
    "application": {
      "gmail_message_id": "abc123",
      "subject": "New application: Example Candidate (Hong Kong)",
      "received_at": "2026-04-06T03:33:47Z",
      "gmail_url": "https://mail.google.com/mail/#all/abc123",
      "source": "gmail/build-club"
    },
    "responses": {
      "current_work": "Running an AI automation agency for e-com operators.",
      "accomplishment": "Scaled agency revenue and shipped internal tooling."
    },
    "extracted": {
      "skills": ["automation", "AI ops", "agency"],
      "motivation_signals": ["self-starting", "ships fast"],
      "ecom_signals": ["works with e-com operators"],
      "ai_padding_signals": []
    },
    "scoring": {
      "overall": 8,
      "motivation": 9,
      "skill_fit": 8,
      "ecom_fit": 8,
      "application_quality": 7,
      "authenticity": 8,
      "rationale": "Strong operator energy with direct AI execution experience.",
      "evidence": [
        "Runs an AI and marketing agency",
        "Describes business outcomes instead of generic claims"
      ]
    }
  }
]
JSON
```

Refresh the markdown report:

```bash
python3 ~/.codex/skills/build-club-applications/scripts/applications_db.py report
```

Export the local full CSV:

```bash
python3 ~/.codex/skills/build-club-applications/scripts/applications_db.py export-csv
```

Export the sanitized public CSV:

```bash
python3 ~/.codex/skills/build-club-applications/scripts/applications_db.py \
  --csv /home/claude/build-club-applications-skill/data/public_candidate_rankings.csv \
  export-csv --public
```

Inspect the current incremental boundary:

```bash
python3 ~/.codex/skills/build-club-applications/scripts/applications_db.py stats --json
python3 ~/.codex/skills/build-club-applications/scripts/applications_db.py list-message-ids
```

Update a manual decision:

```bash
python3 ~/.codex/skills/build-club-applications/scripts/applications_db.py set-status \
  --id example-candidate-abc123 \
  --status shortlist \
  --notes "Strong motivation and practical AI ops background."
```

## Output Expectations
- Keep user-facing summaries concise and ranked.
- Call out the top candidates first.
- Be explicit when a score is dragged down by AI-padded fluff or weak evidence.
- Mention when a candidate looks promising despite limited e-com relevance because motivation is unusually strong.
- The canonical local store is `/home/claude/.local/share/build-club-applications/candidates.json`.
- The default report path is `/home/claude/.local/share/build-club-applications/latest_report.md`.
- The default local full CSV path is `/home/claude/.local/share/build-club-applications/candidates.csv`.
- The public repo artifact should be a sanitized CSV at `/home/claude/build-club-applications-skill/data/public_candidate_rankings.csv`.
