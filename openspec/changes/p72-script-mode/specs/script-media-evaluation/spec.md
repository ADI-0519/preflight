# Script and media evaluation

## Purpose

Measure the difference between screening written ad copy and its rendered development ad using traceable,
paired inputs without changing the frozen split or overstating what the comparison establishes.

## ADDED Requirements

### Requirement: Script comparisons preserve the development boundary
The comparison SHALL select only registered split-v2 development items. It SHALL validate the baseline
cohort before reading item material or labels and reject held-out, void, incomplete or mismatched baseline
runs. It SHALL NOT modify split membership, labels, judge defaults or registered historical results.

#### Scenario: Held-out baseline supplied
- **WHEN** a test-part run is supplied as the media baseline
- **THEN** the comparison fails before opening test content or labels or creating model clients

#### Scenario: Retained baseline is incomplete
- **WHEN** any required baseline screening or original input is missing
- **THEN** the comparison refuses to register a partial result as the complete cohort

### Requirement: Script fixtures derive only from ad copy
Ruling-development scripts SHALL derive only from shot-list voiceover and on-screen copy; team scripts
SHALL derive from their authored ad copy. Assessment text, labels, rule annotations, image prompts,
register IDs and missed-claim analyses SHALL NOT be added to script inputs.

#### Scenario: Shot list includes an image-generation prompt
- **WHEN** the script fixture is built from that shot list
- **THEN** only its advertised words become script lines and its image prompt is excluded

### Requirement: Paired metrics identify their populations
The comparison SHALL report script and baseline media results on the same explicit cohort, including
claim recall, ad recall and negative ads flagged with visible denominators. It SHALL distinguish the
shared textual claim population from claims that only media can express and SHALL preserve incomplete
and unavailable items rather than silently dropping them.

#### Scenario: A visual-only implication has no scripted wording
- **WHEN** a baseline ground-truth claim is absent from the script's supplied words
- **THEN** it is reported outside the paired textual-claim population rather than counted as an observed perception loss

### Requirement: Registered comparisons retain reproducible provenance
Each completed comparison SHALL record script and media run IDs, item IDs, source and script hashes,
source snapshots, code revision, model versions, prompts and voting settings. Failed or unfinished checks
SHALL prevent successful registration. Script inputs and results SHALL remain distinguishable from media runs.

#### Scenario: A complete dev comparison finishes
- **WHEN** all selected script checks finish against a valid retained media baseline
- **THEN** registered run IDs and per-item rows identify the exact compared inputs, configuration and denominators

### Requirement: Claims about the gap stay within the evidence
Reports SHALL call the difference an observed script-versus-media gap. They SHALL disclose modality,
visual-information, extraction-presentation and run-variation limits and SHALL NOT claim a pure causal
perception penalty or held-out performance from a development comparison.

#### Scenario: Script recall exceeds media recall
- **WHEN** the script run catches more claims than the paired media run
- **THEN** the report gives both counts and their cohort and does not attribute the whole difference to perception
