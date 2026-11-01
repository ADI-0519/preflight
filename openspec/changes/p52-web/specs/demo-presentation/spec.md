## ADDED Requirements

### Requirement: Separate recorded screening and ASA outcome
Demo mode SHALL use explicitly labelled reconstructions or synthetic fixtures and
reveal the repository-backed ruling outcome only after the viewer requests it.

#### Scenario: Reveal a reconstruction
- **WHEN** a viewer reveals an explicitly configured reconstruction's outcome
- **THEN** the API returns the ruling date, outcome, rules and URL from the committed
  snapshot, separately from the recorded screening

#### Scenario: View a synthetic fixture
- **WHEN** a viewer reveals a synthetic fixture
- **THEN** the page explains that no ASA outcome exists for that fixture

### Requirement: Registered final scoreboard
The scoreboard SHALL use only the registered test screening run selected by
results/final.md and preserve denominators, intervals and run provenance.

#### Scenario: No final run has been selected
- **WHEN** the selector is absent, ambiguous or identifies a development/unregistered run
- **THEN** the page says final metrics are unavailable and substitutes no other counts

#### Scenario: Valid registered run selected
- **WHEN** one selected test run has consistent metadata and valid rate counts
- **THEN** the page shows registered rates, numerators, denominators, available
  confidence intervals, run ID, split and revision
