# Development tools

These tools are separate from the Python screening runtime. Install the exact lockfile
with `npm ci --prefix tooling`. Node 24 is used on the current workstation.
If this machine needs Windows' certificate store, set `$env:NODE_USE_SYSTEM_CA='1'`;
do not disable TLS verification.

The lockfile overrides transitive `basic-ftp`, `glob` and `minimatch` to patched
versions after npm reported advisories in Promptfoo's dependency tree. The glob and
minimatch overrides cross major versions: local smoke paths are verified, but live
providers and red-team features are not. Keep these overrides under review when
updating Promptfoo; do not apply an automatic forced downgrade.

## Independent Copilot review

Prepare a small text packet with the intended behavior, selected source/diff, test
results and concrete review question. Never include credentials, raw customer media,
partner downloads or held-out evaluation inputs/labels. Only the prepared packet and
repository instructions are supplied; the reviewer has no file, shell or web tools.

```powershell
node scripts/copilot_review.cjs data/work/review-packet.txt data/work/review-001
```

The output directory must be new and its parent must exist. The command has a
three-minute timeout, saves the reply and exit status under ignored `data/work/`, and
fails on an empty reply or failed process. An optional third argument selects a model
that your Copilot account actually supports. An unspecified model uses the CLI's
configured default; this is not proof of Claude access. Calls consume Copilot allowance.
The wrapper removes common unrelated model API keys from the child environment.
It does not resume or control the editor's existing Copilot chat.

## Context7

The workspace's `.vscode/mcp.json` configures the hosted Context7 MCP endpoint for
VS Code; `.mcp.json` configures it for Claude Code if used later. No token is stored.
Use **MCP: List Servers** in VS Code, select Context7 and start it if prompted.
Client discovery/approval is separate from the endpoint connectivity test. This does
not automatically add tools to an already-running assistant session.

Verified on 1 November: the coordinating editor session exposed Context7's native
MCP tools and successfully retrieved public Pydantic documentation. This verifies
that session, not every agent/provider configuration.

Use public library names and generic documentation questions only. Never send private
code, credentials, customer content or evaluation data in documentation queries.
If an account is required for your quota, authenticate through the client; keep keys
out of tracked workspace configuration.

## OpenSpec

```powershell
$env:OPENSPEC_TELEMETRY='0'
npm --prefix tooling run spec -- list
npm --prefix tooling run spec -- new change descriptive-feature-name
```

Use OpenSpec for bounded upcoming work. Existing plan, product rules and decisions
remain authoritative. Do not backfill unverified product capabilities as implemented
specifications. Generated apply/archive templates do not authorize commits, pushes,
deployments, spending or changes to frozen evaluation data.

## Promptfoo

```powershell
$env:PROMPTFOO_DISABLE_TELEMETRY='1'
npm --prefix tooling run eval:smoke
```

The custom identity provider is deliberately offline. Passing this check proves only
that the evaluation tool can load a provider and run an assertion. It measures no
model, screening accuracy or policy validity. The native evaluation registry and split
protocol remain authoritative. Live providers require an explicitly scoped budget
and approved synthetic/dev inputs before use.

## Browser verification

```powershell
uv sync --locked --extra page
$env:NODE_USE_SYSTEM_CA='1'
tooling/node_modules/.bin/playwright.cmd install chromium
uv run --offline python scripts/verify_screening_replay.py --out data/work/replay-browser-001
$env:PREFLIGHT_REPLAY_REPORT=(Resolve-Path data/work/replay-browser-001/report.html).Path
npm --prefix tooling run browser:test
```

The browser test checks the generated synthetic report and blocks network requests.
It verifies visible limitations, a claim and its policy reference. It does not establish
live accuracy or cover the future upload/API/re-screening journey. Missing report
configuration fails the test rather than skipping it. Screenshots/traces, if added,
must stay under ignored `data/work/`.

## Langfuse

```powershell
npm --prefix tooling run trace:check
```

This verifies SDK presence and checks environment variable names without creating a
client, printing values or uploading traces. Exit 2 means account configuration is
still missing. It does not establish connectivity or working instrumentation.

Choose a local instance or create a free Langfuse Cloud account, then set
`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_BASE_URL` outside tracked
files. Docker Desktop must be running for local hosting. Do not enable automatic
screening/model instrumentation: first implement and verify a metadata-only trace
allowlist using synthetic data. Raw prompts, media, model output, credentials and
customer/partner data must not be captured by default.

Official references: [Context7](https://context7.com/docs/clients/vscode),
[OpenSpec](https://github.com/Fission-AI/OpenSpec),
[Copilot automation](https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically),
[Playwright](https://playwright.dev/docs/intro),
[Promptfoo](https://www.promptfoo.dev/docs/intro/),
[Langfuse hosting](https://langfuse.com/self-hosting/deployment/docker-compose).
