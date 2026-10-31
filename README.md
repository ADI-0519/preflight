# PreFlight

PreFlight screens a health or supplement ad before it goes live. Give it a video, an image or a product-page screenshot and it finds every health claim, including claims implied by imagery, checks each against the GB nutrition and health claims register, the CAP Code and past ASA rulings, and shows for every flag the evidence (a transcript timestamp or an on-screen region) and the source it conflicts with. Where the register authorises a claim on the same substance, PreFlight quotes that wording exactly as the fix.

It is screening, not legal advice. It flags and explains; a person decides whether the ad runs. The rules the product follows are in [docs/product-rules.md](docs/product-rules.md).

## How we will know it works

The ASA publishes its rulings, and each one says which claims in an ad broke which rules. We hold back the most recent rulings, rebuild each ad from the ruling's description of it, and let PreFlight screen it without seeing the ruling. Alongside them sit ads that use only authorised register wording. We report how many breaches PreFlight caught and how many compliant ads it wrongly flagged, on a frozen, versioned test split, against a keyword baseline that uses no models. The protocol is in [docs/plan.md](docs/plan.md#evaluation-protocol-contract-for-p14-and-p31).

## Pipeline

```
ad (video | image | page screenshot)
  ├─ voiceover → Muse Voice Transcribe → text with word timestamps
  ├─ frames → SAM 3.1 tracks text overlays, packaging, before/after shots → Muse Spark reads each region
  ├─ Muse Spark extracts every claim, explicit or implied, tied to its evidence
  ├─ each claim checked against the register, CAP Code rules and past rulings → flags with sources
  └─ report; an agent can swap flagged claims for register wording and re-check before a person approves
```

## Setup

Needs [uv](https://docs.astral.sh/uv/). It installs Python 3.12 if missing.

```
uv sync
cp .env.example .env    # then fill in META_API_KEY
uv run pytest           # skips tests marked live
uv run ruff check
```

Tests that call the real Meta Model API are marked `live` and run only with `uv run pytest -m live`.

## Status

Work in progress for the Meta Global AI Developer Hackathon (submission 4 November 2026). The plan, architecture and task list are in [docs/plan.md](docs/plan.md); tasks are tracked as issues on the project board.

| Path | What |
|---|---|
| `docs/plan.md` | Architecture, evaluation protocol, lanes and tasks |
| `docs/product-rules.md` | The ten rules every output and evaluation follows |
