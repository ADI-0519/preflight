# PreFlight

PreFlight screens a health or supplement ad before it goes live. Give it a video, an image or a product-page screenshot and it finds every claim the ad makes, including claims implied by imagery: health claims, and claims about the product or its rivals that could mislead. It checks each against the GB nutrition and health claims register, the CAP Code and past ASA rulings, and shows for every flag the evidence (a transcript timestamp or an on-screen region) and the source it conflicts with. Where the register authorises a claim on the same substance, PreFlight quotes that wording exactly as the fix.

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

For an inspectable synthetic replay with no credentials or network requests (requires FFmpeg):

```powershell
uv run --offline python scripts/verify_screening_replay.py --out data/work/verification/replay-001
```

Choose a new output directory on each run. It writes labelled HTML, screening JSON and a provenance manifest. This checks recorded-response contracts and rendering, not live model accuracy or ruling-text retrieval. See [the development workflow](docs/notes/engineering-workflow.md) for the research, limitations and next verification steps.

## Use as a tool

Other agents can call PreFlight as two tools: `screen_ad` (screen a video, image or page) and `fix_ad` (screen a draft and swap flagged lines for register wording). `screen_ad` returns the flagged lines, each with its CAP rules, sources, evidence and any register wording, a shorter flagged phrase on the same evidence folded under the line that contains it, and the register's authorised entries for each flagged substance. A draft can be just a script, voiceover and on-screen text with no picture, which `fix_ad` renders on a plain card. There is no approve or publish tool. A person records approval with `preflight approve <log> --by <name>`.

To serve them to an MCP client over stdio, install the extras (`uv sync --extra mcp --extra render`) and add this to the client's config, with the path to this repository:

```json
{"command": "uv", "args": ["run", "--directory", "<path to repo>", "--extra", "mcp", "--extra", "render", "preflight", "mcp"]}
```

The tools read any file path or URL the calling agent passes, and send the ad to the Meta Model API, so connect them only to agents you trust. Results are written under `data/work/agent/`.

`scripts/agent_demo.py <draft.yaml>` shows an agent given a draft ad that calls `screen_ad` before it would publish. It needs the `render` extra.

## Status

The [web workspace guide](docs/web.md) covers building and running P52, synthetic
browser verification, demo asset configuration and the registered-run scoreboard.

The [local API guide](docs/api.md) documents P51 endpoints, SSE, retention and the
localhost run command. API verification uses synthetic replay, not live models.

Optional agent coordination, Context7, OpenSpec, Promptfoo, browser checks and tracing
setup are documented in [the development toolkit](tooling/README.md).

Work in progress for the Meta Global AI Developer Hackathon (submission 4 November 2026). The plan, architecture and task list are in [docs/plan.md](docs/plan.md); tasks are tracked as issues on the project board.

| Path | What |
|---|---|
| `docs/plan.md` | Architecture, evaluation protocol, lanes and tasks |
| `docs/product-rules.md` | The ten rules every output and evaluation follows |
