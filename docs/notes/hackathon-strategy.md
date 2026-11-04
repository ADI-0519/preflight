# Evidence-backed hackathon strategy

**Updated:** 4 November 2026
**Scope:** Meta Global AI Developer Hackathon and the PreFlight submission

## Submission-day assessment

Recommendation: keep the product, narrow the buyer and sharpen the demonstration.
Position PreFlight as an evidence-backed review workspace for UK supplement-agency
creative: check the script before production, then screen the finished cut. These
are two supported screening journeys, not an implemented automatic script/cut diff.
Do not promise approval, exhaustive detection or replacement of expert review.

### Correct judging weights

The fully rendered [Official Rules and Event Waiver](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver),
read in the browser on 4 Nov, specify impact **30%**, Meta tooling **25%**, technical
depth/execution **20%**, and demo **25%**. This corrects the earlier equal-weight
participant summary in our notes. The public landing page discusses application
selection separately; its equal weighting is not the project rubric. Public
text-only retrieval of the waiver returned a loading placeholder. See the updated
[rules record](hackathon-rules.md) for source status and unresolved founder checks.

The [official event page](https://dev.meta.ai/events/global-hackathon) still gives
4 Nov, 9 PM ET as the submission deadline: 5 Nov, 02:00 GMT. Keep the issue's
earlier 4 Nov, 21:00 GMT target as an internal buffer, not as the official deadline.

### What remains on GitHub

Live issue check on 4 Nov: eight open issues. Closed implementation issues include
P33, P43, P60, P70 and P71; closing those does not establish deployment readiness.

| Open issue | Remaining delivery | Priority today |
|---|---|---|
| [P69 / #72](https://github.com/ADI-0519/preflight/issues/72) | Record organiser answers on category and reconstruction use, or the date questions were sent. Reading the rules alone does not resolve these questions. | Founder action immediately; team-made demo assets are the fallback. |
| [P53 / #29](https://github.com/ADI-0519/preflight/issues/29) | Choose exact demo assets and document run IDs; any showcase render needs its own screening. NEESAY is assigned. | Critical path to recording. Coordinate before duplicating their work. |
| [P54 / #30](https://github.com/ADI-0519/preflight/issues/30) | Record, caption and export the under-three-minute video. | Critical. |
| [P55 / #31](https://github.com/ADI-0519/preflight/issues/31) | README with measured results, limits, reproducible setup; secrets/rights review; authorised public release and logged-out check. | Critical. Repository was PRIVATE at inspection. |
| [P68 / #71](https://github.com/ADI-0519/preflight/issues/71) | Hosted, logged-out demo with private host key and public limits; issue permits demos-only or run-instruction fallback. | High, time-boxed; no public URL verified in this review. |
| [P56 / #32](https://github.com/ADI-0519/preflight/issues/32) | Submit all teammates, working video/repository links and confirm receipt. | Critical; reserve time for link and eligibility checks. |
| [P72 / #84](https://github.com/ADI-0519/preflight/issues/84) | Script delivery implemented and pushed; original retained dev bundle required for registered paired measurement. | Ask teammate for assets; do not hold up recording to invent a metric. Keep issue open. |
| [P06 / #6](https://github.com/ADI-0519/preflight/issues/6) | Partner response/consent, or record the decision to use team ads. | Valuable impact evidence; no outreach or quotation invented by the agent. |

P72 has been pushed to its branch but no P72 PR was listed at inspection. Existing
PR82 is an older reconciliation branch; PR87 contains older stress/diagnostic work
and a change to judge retries. Neither should be merged wholesale into the frozen
submission configuration merely to reduce the number of open PRs.

### Evidence we can defend

The registered [final results](../../results/final.md), run
`screen-20261104T052428`, report:

- 54/59 positive reconstructed ads flagged, compared with 28/59 for the keyword baseline.
- 334/530 carried breaching claims caught with a matching rule (63.0%), compared
  with 47/530 (8.9%) for the baseline. Our agreed 70% claim target was **not met**.
- 1/20 negative ads flagged; the exact 95% interval is approximately 0.1–24.9%.
  Twenty negatives do not establish a dependable 5% real-world false-alarm rate.
- 10/10 near-miss lines caught, 0/77 clean lines flagged in those items. The
  bootstrap zero-width interval on zero observed clean-line flags is not proof of
  zero risk; show counts and the small evaluation population.
- 368 unmatched flagged lines across 59 positive ads. Unmatched does not mean
  wrong, because the ASA annotations are not exhaustive, but this is substantial
  reviewer workload and cannot be hidden behind ad-level recall.
- $24.15 for 79 items in this evaluation; it is not a production price quote.

These are reconstructed-ad and team-written evaluation results, not real-customer
accuracy. Preserve the original registered run and its documented retry/replay
history. Do not tune against the revealed test split or substitute a subsequent
experiment as the original held-out result.

The scoreboard integration gap reproduced during the original review is resolved
by the merged P73 work: the report generator now emits the standalone `run_id:`
selector, and the actual web page was checked against the registered final run.
Historical metrics remain unchanged. The README also still describes finding every
claim and presents evaluation in future tense; revise both against actual results.

### How to earn points

| Criterion | Submission proof | Weak claim to avoid |
|---|---|---|
| Impact, 30% | One named buyer role: the UK supplement agency's creative reviewer. Show the rejected wording, where it occurs, the sourced alternative and the review decision. Add a genuine partner quote or a measured manual-vs-assisted task if available. | Invented savings, market size, pilots, or claims that regulatory screening guarantees platform acceptance. |
| Meta tooling, 25% | In the same ad, show a spoken claim, visible caption/region evidence, structured Spark checking, then a constrained render and re-screen. Label actual model roles. | A model-name montage, or implying the optional open-weights triage is a validated production capability. |
| Technical execution, 20% | Exact line/time evidence, versioned sources, verified register wording, bounded fix loop, saved audit trail, incomplete states and reproducible benchmark against the baseline. | Test counts as proof of model accuracy or universal production readiness. |
| Demo, 25% | A readable before/after artifact and one coherent user journey; no dead links, logins or long waits. Preloaded genuine saved results as an explicitly labelled fallback. | Synthetic replay represented as a live model run, fabricated progress, or a speculative feature shown as shipped. |

### Comparable winners and the inference we should draw

[Meta's LlamaCon account](https://ai.meta.com/blog/llamacon-hackathon/) names
OrgLens first, Compliance Wizards second and Llama CCTV Operator third. OrgLens
connected organisational records to expert discovery; Compliance Wizards combined
transaction risk with follow-up actions; CCTV Operator translated operator-defined
events into video alerts. The [OrgLens repository](https://github.com/TheCl3m/llama-hack)
puts a concrete problem, demo and setup together. This is evidence that a focused
professional workflow can win at Meta, not proof of which presentation choice
caused its ranking.

In [Anthropic and Cerebral Valley's Opus 4.6 winner account](https://claude.com/resources/articles/meet-the-winners-of-our-built-with-opus-4-6-claude-code-hackathon),
first-place CrossBeam addresses a narrow permit/correction workflow; TARA turns
road footage into a usable appraisal artifact. My inference is that domain insight
plus a completed task is a stronger story than another general AI assistant.
These are different contests and do not establish this event's scoring outcomes.

Advertising review itself is not new: [Adclear](https://www.adclear.ai/) markets
AI-assisted financial-promotion review and governance. Do not claim PreFlight is
the first AI compliance tool. Our proposed distinction is a narrow GB supplement
workflow, multimodal source evidence, exact-register substitutions, both script
and finished-cut checks, and a disclosed benchmark. Buyer demand and willingness
to pay still need validation; competitor marketing is not that validation.

The [ASA's October Pulse Report page](https://www.asa.org.uk/resource/pulse-report-health-claims-in-online-ads.html)
describes widespread likely breaches in seven priority health-ad topics. It supports
the problem's relevance. It does not quantify our addressable market or prove the
percentage of all ads that are illegal.

### Recommended three-minute story

| Time | Show |
|---|---|
| 0:00–0:15 | A legible team-made ad with a risky claim. Name the agency reviewer and the cost of discovering problems after filming, without inventing a money figure. |
| 0:15–0:35 | Script input: one quoted line, CAP source and scope notice. Explain that the finished ad still needs checking. |
| 0:35–1:10 | Finished cut: spoken and on-screen evidence; select a claim and show its exact source. |
| 1:10–1:45 | A supported revision: exact registered wording, changed artifact, re-screen, explicit human review. This is the main reveal. |
| 1:45–2:10 | Held-out comparison: 54/59 ads and 334/530 carried claims, baseline alongside, 1/20 negatives and limitations. Do not call 91.5% ad recall accuracy. |
| 2:10–2:35 | Model roles and the checks around them; show a failure staying incomplete or one honest miss, not a code tour. |
| 2:35–2:55 | Buyer, honest pilot status, live/replay entry point and next validation step. Finish below three minutes. |

Before recording, verify each displayed render with actual model responses and save
its provenance. A showcase render is a new input even if its copy is unchanged.
Where the recording skips wait time, mark the cut/time lapse. A replay fallback
must identify the original saved run; the browser-test server's fabricated answers
must never serve as a real screening demonstration.

Today's order: founder category/asset confirmation and P53 coordination; successful
real-model showcase capture; scoreboard/README and logged-out reproducibility;
video; authorised deployment/publication; submission verification. P72 paired
measurement can run in parallel only if its original assets and working credentials
are available. Defer a new jurisdiction, autonomous publishing, new model defaults,
brand monitoring and automatic script/cut drift detection.

The sections below are earlier background research. The current assessment above
supersedes their submission-readiness assumptions; their paper reading list is not
evidence that any particular coding setup or model budget wins hackathons.

This document separates verified facts, observed precedent, research findings, and team hypotheses. It is a strategy aid, not a claim that any result is guaranteed.

## Executive conclusion

Unlimited model calls or unlimited agent runtime are not, by themselves, a winning advantage. The strongest evidence points to a tighter loop:

1. choose one painful, specific workflow;
2. use Meta models in roles that are visibly necessary;
3. produce a deterministic, judgeable artifact;
4. measure it against a frozen benchmark;
5. show recovery, provenance, and human control;
6. keep the demo and public repository legally defensible.

For PreFlight, the highest-leverage artifact is a constrained multimodal fix loop: detect an advertising claim, show its evidence and source, replace it only with exact authorized wording, re-screen it, and record the audit trail.

## Confirmed competition facts

The official Meta event page confirms the two tracks, the two themes, the Meta model families, the November 4 submission deadline at 9:00 PM ET, judging from November 4–8, and winners on November 9: [Meta Global AI Developer Hackathon](https://dev.meta.ai/events/global-hackathon).

The participant FAQ supplied by the team additionally states that the project must be new work, the repository must be public, the video must be three minutes, all contributors must be approved, and prohibited categories include AI medical advice, nutrition coaches, generic RAG, and simple image analyzers. The rendered formal rules were read on 4 Nov; founder eligibility, acceptance and the category/asset questions still require confirmation. See [hackathon-rules.md](hackathon-rules.md).

## What the closest Meta winners demonstrate

Meta's official LlamaCon winner report is the strongest public precedent available for this event: [Meet the winners of our first-ever LlamaCon Hackathon](https://ai.meta.com/blog/llamacon-hackathon/).

- **OrgLens:** multiple data sources became a knowledge graph, contributor profiles, natural-language search, and digital twins. The public [winning repository](https://github.com/TheCl3m/llama-hack) includes a frontend, backend, setup instructions, and a demo artifact.
- **Compliance Wizards:** multimodal transaction analysis became risk scoring, notifications, and a voice interaction.
- **Llama CCTV Operator:** natural-language event definitions became repeated video inspection and operator alerts without fine-tuning.
- **Geo-ML:** long technical reports became a structured domain representation and a 3D geological artifact.

Observed pattern, not a published judging formula: winning entries turn model capability into a user workflow with a visible artifact and a short proof that the system works. They do not stop at a chat response or an API wrapper.

## Research-paper reading list

These papers are linked rather than copied into the repository. The links are the canonical paper pages; summaries below are intentionally short.

### Agent design and feedback

1. [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)

   Interleaving reasoning with tool actions helps agents update plans and handle exceptions. For PreFlight, each model decision should be paired with an observable tool result: source lookup, evidence lookup, re-screening, or validation.

2. [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)

   Agents can improve through external feedback stored as textual reflection rather than weight updates. For PreFlight, failed checks should produce a compact failure record and a bounded retry, not an unbounded self-conversation.

3. [SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering](https://arxiv.org/abs/2405.15793)

   Tool interface design materially changes agent performance. The lesson for the hackathon is to expose small typed tools with clear inputs and outputs, not one giant tool that hides all state.

4. [Agentless: Demystifying LLM-based Software Engineering Agents](https://arxiv.org/abs/2407.01489)

   A simple localization → repair → validation pipeline performed strongly at low cost in its benchmark. This is a warning against adding sub-agents merely to look sophisticated; PreFlight should use the simplest loop that proves the product claim.

5. [When Sub-Agents Work in Parallel: The Promises and Pitfalls of Dynamic Concurrency in Long-Horizon Coding Tasks](https://arxiv.org/abs/2610.10263)

   A 2026 preprint studying 2,124 executions reports that orchestration becomes more important as tasks get longer and identifies concurrency-specific failure modes. Treat this as recent, not yet settled evidence: parallel workers need isolated scopes, shared artifacts, and a coordinator that resolves conflicts.

### Evaluation and agent reliability

6. [SWE-Skills-Bench: Do Agent Skills Actually Help in Real-World Software Engineering?](https://arxiv.org/abs/2603.15401)

   A 2026 preprint reports that most tested skills produced no pass-rate improvement, with some increasing token cost or degrading results. Skills must therefore be narrow, tested, and selected only when relevant. This validates the small repository skill set in `.agents/skills/` rather than a large skill bundle.

7. [SWE-Bench Pro Verified: A Reliable Benchmark for Software Engineering Agents](https://arxiv.org/abs/2609.08149)

   The paper focuses on leakage, reward hacking, and flawed task specifications. The direct PreFlight lesson is to freeze evaluation data, keep held-out rulings out of prompts and retrieval, and verify results in a clean environment.

8. [SWE-Bench Pro V2: A Cleaner, Harder-to-Game Coding Benchmark](https://arxiv.org/abs/2610.24206)

   The 2026 preprint hardens benchmark construction through audits, blind reimplementation, and clean re-grading. PreFlight should apply the same principle: report reconstruction performance separately from performance on consenting or synthetic ads, and never call the reconstruction score real-world accuracy.

9. [PlanBench: An Extensible Benchmark for Evaluating Large Language Models on Planning and Reasoning about Actions](https://arxiv.org/abs/2206.10498)

   Planning should be tested by executable consequences rather than by asking an agent whether its plan sounds good. PreFlight's agent should be judged by whether a revised ad actually passes its checker, not by the quality of its explanation.

### Hackathon and innovation-contest evidence

10. [You Hacked and Now What?: Exploring Outcomes of a Corporate Hackathon](https://cscw.acm.org/2018/program/toc.html)

   This case study reports that projects which continued after the event were characterized by preparation, a shared vision during the hackathon, dissemination afterward, and fit with an existing product line. It is not evidence about Meta's scoring, but it supports investing in a coherent product narrative and a public artifact.

11. [womENcourage hackathon judging criteria](https://womencourage.acm.org/2020/hackathon/)

   This is event guidance rather than a research paper, but it explicitly scores innovation, creativity, execution, impact/business model, and presentation. The overlap with the Meta participant rubric supports treating the demo as a first-class deliverable rather than a final recording chore.

## Implications for PreFlight

### Strongest fit

PreFlight fits **Build for Your World** if framed as advertising-risk infrastructure for people who review regulated creative. It must not be presented as product efficacy advice, medical advice, or a nutrition coach.

### Strongest technical story

```text
ad media
  → Muse Voice Transcribe: spoken evidence
  → SAM 3.1: visual regions and tracks
  → Muse Spark: claims and structured reasoning
  → source checker: register, CAP, and ruling references
  → human-readable finding with evidence
  → constrained rewrite using exact register wording
  → re-screen and audit log
```

Meta model use is meaningful only if removing a model breaks a visible capability. A model-name montage is weak evidence.

### Critical risks

1. **Prohibited-category ambiguity:** health-product advertising may be mistaken for medical advice or a nutrition coach. Ask the organisers in writing.
2. **Third-party content rights:** obtain written permission for ASA-derived reconstructions or use synthetic/consented assets.
3. **Evaluation leakage:** the held-out ruling must not enter prompts, retrieval, examples, or tuning.
4. **New-work proof:** submit a standalone public repository and document the event-period contribution clearly.
5. **Overclaiming:** call it a reconstruction benchmark, not real-ad accuracy; keep the human decision in the loop.

## Evidence-gated execution plan

### Gate 0 — eligibility, before more feature work

- Read the formal rules from the logged-in event page.
- Get written answers on the health-category and ASA-content questions.
- Confirm every contributor was approved.
- Decide Indie versus Startup based on actual eligibility.

### Gate 1 — judgeable vertical slice

- One synthetic or licensed ad enters the system.
- At least one claim has transcript or region evidence.
- At least one source-backed flag renders.
- The report uses the exact product wording rules in [product-rules.md](../product-rules.md).

### Gate 2 — constrained agent loop

- The agent can select only existing register wording.
- The revised artifact is screened again.
- A failed validation stops the loop and explains why.
- Maximum retries and budget are explicit.

### Gate 3 — evaluation proof

- Freeze the split before prompt tuning.
- Include positives and credible negatives.
- Report breach recall and false-alarm rate separately.
- Keep reconstruction results and real/consented results in separate tables.

### Gate 4 — submission artifact

- Fresh public repository.
- Three-minute video opens with the problem, user, and Meta model contribution.
- Logged-out clone/setup works.
- No keys, private media, unsupported claims, or unlicensed assets.

## Bottom line

The evidence does not support the claim that the winner simply has unlimited processing. The defensible advantage is **more validated attempts per unit time**: parallelize independent research and implementation tasks, but use deterministic checks, frozen evaluation, isolated workspaces, and a single coordinator. For PreFlight, a smaller reliable agent loop with provenance is strategically stronger than a large autonomous swarm that produces an impressive but unverifiable demo.
