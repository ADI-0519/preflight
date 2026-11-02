# Screening API

## Purpose

Let the web client screen retained uploads, follow progress and request draft fixes
while keeping policy decisions in the existing pipeline and human review explicit.

## ADDED Requirements

### Requirement: Screening jobs preserve evidence and provenance
The API SHALL call the existing screen function, verify every returned screening's
sources, and distinguish completed, incomplete and failed jobs.

#### Scenario: Replayed screening
- **WHEN** a valid retained upload starts a screening
- **THEN** the job exposes its screening with evidence, sources and notice

#### Scenario: Incomplete screening
- **WHEN** a stage fails or the check does not finish
- **THEN** the API exposes an incomplete result without presenting it as a clean check

### Requirement: Job progress can be resumed
The API SHALL stream ordered SSE events and honor Last-Event-ID without repeating
earlier events. Events SHALL contain status metadata rather than private ad content.

#### Scenario: Reconnect after completion
- **WHEN** a client reconnects with an event ID
- **THEN** only subsequent events are returned and the terminal stream closes

### Requirement: Fixes require a separate human decision
The API SHALL reuse the existing fix and approval functions. It SHALL validate stored
screening sources before fixing or approving and reject incomplete or flagged approval.

#### Scenario: Explicit approval
- **WHEN** a completed fix awaiting approval receives a named human decision
- **THEN** an approval audit record is appended without claiming platform approval

#### Scenario: Invalid or unfinished result
- **WHEN** an invalid-source, incomplete or flagged result is offered for approval
- **THEN** the decision is rejected and no approval record is appended
