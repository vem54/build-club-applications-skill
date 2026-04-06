# Build Club Applications Skill

Codex skill for triaging Build Club applications from Gmail, scoring candidates with a motivation-first rubric, and persisting a local JSON tracker plus markdown report.

This repo contains the shareable workflow only. It does not include any real applicant data.

## What It Does

- searches Build Club application emails in Gmail through the Codex Gmail connector
- scores candidates from `1` to `10`
- ranks motivation first, then skill, then authenticity, then e-com relevance
- penalizes obvious AI-slop and low-signal founder copy
- stores everything locally as JSON and generates a markdown ranking report
- supports incremental syncs so future runs score only unseen Gmail message IDs

## Skill Layout

- [SKILL.md](./SKILL.md)
- [agents/openai.yaml](./agents/openai.yaml)
- [scripts/applications_db.py](./scripts/applications_db.py)

## Install

Clone or copy this repo into:

```bash
~/.codex/skills/build-club-applications
```

After that, invoke it in Codex with:

```text
Use $build-club-applications to sync and score new Build Club applications from Gmail.
```

## Local Data

By default the helper writes local data to:

```text
~/.local/share/build-club-applications/candidates.json
~/.local/share/build-club-applications/latest_report.md
```

These files stay on your machine and are not meant to be committed.

## Privacy

Do not publish your real `candidates.json` file. It can contain applicant names, contact info, and private notes.

## Helper Commands

Show current tracker stats:

```bash
python3 scripts/applications_db.py stats --json
```

Render the report:

```bash
python3 scripts/applications_db.py report
```

Update a candidate status:

```bash
python3 scripts/applications_db.py set-status --id candidate-id --status shortlist --notes "Strong operator profile."
```
