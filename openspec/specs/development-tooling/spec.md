# Development tooling

## Purpose

Provide repeatable optional development tools without changing screening behavior,
evaluation splits or the repository's approval requirements.

## Requirements

### Requirement: Independent review receives explicit context

The Copilot review wrapper SHALL accept a deliberately prepared text packet and SHALL
disable reviewer tools. It SHALL fail on process failure, timeout or an empty reply.

#### Scenario: Review succeeds
- **WHEN** the CLI returns a nonempty reply with exit status zero
- **THEN** the wrapper saves the reply and status in a new directory under data/work

#### Scenario: Review output already exists
- **WHEN** the requested output directory already exists
- **THEN** the wrapper refuses to overwrite it before calling Copilot

### Requirement: Smoke checks do not establish model quality

The optional Promptfoo and browser smoke checks SHALL describe their synthetic scope
and SHALL NOT be reported as evidence of live screening accuracy.

#### Scenario: Offline evaluation smoke
- **WHEN** the Promptfoo smoke configuration is run
- **THEN** a local identity provider checks tool plumbing without calling a model

### Requirement: External tooling preserves data boundaries

Documentation queries SHALL contain only public library questions. Tracing SHALL remain
unconnected to the screening pipeline until a metadata-only allowlist is verified.

#### Scenario: Tracing readiness check
- **WHEN** the Langfuse readiness script runs
- **THEN** it reports configuration presence without printing credential values or sending traces
