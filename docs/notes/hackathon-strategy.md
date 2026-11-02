# Evidence-backed hackathon strategy

**Updated:** 1 November 2026  
**Scope:** Meta Global AI Developer Hackathon and the PreFlight submission

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

The participant FAQ supplied by the team additionally states that the project must be new work, the repository must be public, the video must be three minutes, all contributors must be approved, and prohibited categories include AI medical advice, nutrition coaches, generic RAG, and simple image analyzers. The formal rules should still be read from the logged-in event page before submission; see the unresolved items in [hackathon-rules.md](hackathon-rules.md).

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
