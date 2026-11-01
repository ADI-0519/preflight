# Evidence-driven development for the remaining hackathon work

Research and initial implementation: 1 November 2026. This is a project-specific recommendation, not a prediction of placing. Competition evidence is in the participant material supplied by ADI-0519; the current supplied rubric is impact 30%, Meta tooling 25%, technical execution 20%, demo 25%. The existing plan and product rules remain authoritative.

## What was independently inspected

The [original starter's forks](https://github.com/advitrocks9/aichessathon-starter/forks) identify the relevant project; the detailed inspection focused on [TobyCoad's fork](https://github.com/TobyCoad/aichessathon-starter), not an exhaustive audit of every competitor. Read the handover, recurring prompt, loop script, statistical test, selected journal passages and evaluation architecture. No third-party automation was executed or copied into PreFlight.

Toby's [handover](https://github.com/TobyCoad/aichessathon-starter/blob/main/README-HANDOVER.md) describes a known champion, challenger directories, explicit correctness and time-control gates, clean-unzip validation, persistent notes and a journal. It also records expensive mistakes: accidentally testing the champion against itself, interrupted edits, and resource contention distorting results. Borrow the preservation of a verified candidate and the habit of recording failures. The historical handover says mid-table at that time; it does not establish the final placing or prove that this workflow caused success.

His [SPRT implementation](https://github.com/TobyCoad/aichessathon-starter/blob/main/testing/sprt.py) records a simulation in which an early unguarded test accepted neutral changes 14% of the time against a nominal 5%, motivating a minimum sample guard. This is an author-reported calibration, not independently reproduced here. The general lesson is to test the evaluator itself and pair comparisons on identical inputs. Chess Elo and its stopping thresholds do not transfer directly to ad screening.

The [recurring prompt](https://github.com/TobyCoad/aichessathon-starter/blob/main/overnight/continuous/PROMPT.md) even permits some positive but inconclusive results to advance under the author's chosen rules. Therefore, describing this as universally strict statistical promotion would overstate it. The [loop](https://github.com/TobyCoad/aichessathon-starter/blob/main/overnight/continuous/loop.sh) automatically pulls/pushes and bypasses permission prompts. These are not adopted: PreFlight preserves its explicit human permissions and single-writer checkout.

Anthropic's [long-running-agent engineering report](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents) describes incremental feature work, durable progress artifacts and testing in a browser because unit-level success could conceal broken user journeys. This is engineering evidence from their application setting, not a ranking of tools or evidence that multiple agents always outperform one.

The [Playwright agent documentation](https://playwright.dev/docs/test-agents) confirms planner, generator and healer roles. It explicitly allows the healer to return a skipped test when functionality appears broken. A skipped critical journey must therefore remain missing evidence in our release decision; it must not silently become a green gate.

## Recommendation for PreFlight

Keep the existing Python/uv/Ruff/pytest pipeline and planned React/FastAPI interface. The attached research's generic Next.js rewrite, deployment-first plan and new documentation hierarchy do not fit this established repository. Continue using [the plan](../plan.md), [product rules](../product-rules.md), [decision record](../notes/decisions.md) and [handoff](../handoff-2026-11-01.md), rather than creating competing PRODUCT/ARCHITECTURE/STATE sources of truth.

Use the existing assistant for bounded implementation. Bring in an independent read-only reviewer when there is a concrete diff and a reproducible acceptance test. A second subscription is optional. Following the user's request, the optional [development toolkit](../../tooling/README.md) now adds pinned OpenSpec, Promptfoo, Playwright and Langfuse SDK packages, Context7 workspace configuration and a restricted Copilot CLI review wrapper. No subscription was purchased. Promptfoo's offline smoke does not replace the native evaluation registry, and Langfuse instrumentation is not enabled in the screening pipeline. Account configuration and client activation are separate from package installation; see the toolkit for limitations.

One cycle:

1. Select one documented user-visible failure or capability and state the hypothesis.
2. Name the baseline, exact inputs, source versions, acceptance criteria and resource ceiling before execution.
3. Implement one bounded change on the existing branch. Do not run another writer in this checkout.
4. Run focused regressions, repository checks and the inspectable replay.
5. For model-quality claims, compare paired dev outputs and have a person review disagreement and source meaning. Keep the frozen held-out test set out of development. Small/noisy gains remain inconclusive.
6. Record results and limitations in the existing notes/registry. Promote a candidate only after the applicable gates and human review; no automatic commit, push, deployment or spending.

## Started: an inspectable offline baseline

Run from the repository root, choosing a new output directory each time:

```powershell
uv run --offline python scripts/verify_screening_replay.py --out data/work/verification/replay-001
```

The command runs media ingestion, evidence extraction, claims, checking, source validation, JSON round-trip and HTML rendering using existing synthetic recordings. Cache mode is replay-only and HTTP transports refuse requests. It does not load credentials or fall back to live inference. An existing output directory is refused to preserve previous evidence.

Outputs: screening JSON, a clearly labelled replay HTML report and a manifest with input hashes, current HEAD/dirty state, source fingerprint, snapshot/model/prompt versions and output hashes. The fingerprint identifies the working source content; it is not a source archive and does not make a dirty run reconstructible from its commit alone.

Limitations are explicit in both the report and manifest: the video and speech are separate synthetic fixtures, there is no ruling-text retrieval, word alignment is disabled, and recorded responses do not establish live accuracy. This is a contract/rendering baseline, not a benchmark score and not the final advertised product journey.

Browser inspection found the expected three claims and one flag, with its on-screen timing and two CAP references. It also exposed why semantic review matters: the recorded explanation asserts that the product is not a licensed medicine, which the shown media does not establish. Retain this as a review finding; passing the replay must not certify that explanation as fact. The existing response fixture was not rewritten to make the finding disappear.

## Next actions, in priority order

1. Inspect this replay report and establish reviewer expectations for evidence grounding and unsupported premises. Preserve any failure as a regression or labelled dev review case.
2. Prepare three complete synthetic media inputs for a budgeted live smoke test: a clear source-backed issue, authorised wording in context, and mixed substances/visual implications. Authorise the exact live calls and cost ceiling before running them; no calls were made in this task.
3. Coordinate with the teammate's P31 and P41 work. Render negative ads through the full pipeline, add a credible baseline, and record source relevance, evidence grounding, false flags, incomplete runs, cost and latency separately. Avoid reducing these to one accuracy score.
4. Implement the P51/P52 user journey around the existing pipeline. Add ordinary Playwright user-journey tests when the UI exists, including incomplete/error recovery. No autonomous test healing or new test-agent installation is needed now.
5. Freeze the evaluated configuration and record the exact event-period contribution; run held-out evaluation only under the agreed protocol. Record the three-minute demo from actual capabilities, label replay/live states, and submit early. Hosting remains outside the existing pre-submission scope unless the founders change the plan explicitly.

The competitive hypothesis is that an advertiser can go from a visible multimodal claim to inspectable evidence, a dated source, a constrained revision and re-screening. The differentiator must be demonstrated and measured; more agents, papers or commit volume are not substitutes for that outcome.
