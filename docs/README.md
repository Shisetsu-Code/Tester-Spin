# Tester-Spin documentation index

Use this directory as the technical continuity point for the project.

## Core documents

- [HANDOFF.md](HANDOFF.md) — general architecture, provider status and operational handoff.
- [PROTOCOLS.md](PROTOCOLS.md) — observed protocol contracts by provider.
- [OPERATIONS.md](OPERATIONS.md) — execution, updater and debugging workflow.
- [EXHAUSTIVE_PATH_COVERAGE.md](EXHAUSTIVE_PATH_COVERAGE.md) — provider-neutral definition of `OK` and exhaustive path coverage.

## BGaming

- [BGAMING_PROGRESS_AND_RATIONALE.md](BGAMING_PROGRESS_AND_RATIONALE.md) — current worklog and rationale: why the earlier structure failed, how state/action semantics were cleaned up, why coverage uses scoped selectors and the minimum provider-advertised wager, how GitHub run evidence is published, and how coverage feeds future high-volume sampling and local emulation.
- [BGAMING_EMULATION_CONTRACT.md](BGAMING_EMULATION_CONTRACT.md) — generated backend-facing protocol/state artifacts and the boundary between wire emulation and RNG/math.

## Current development model

The current design separates three stages:

```text
1. DISCOVERY / COVERAGE
   discover every provider/client-demonstrated executable path

2. HIGH-VOLUME SAMPLING
   repeat each normalized path independently hundreds/thousands of times

3. LOCAL EMULATION
   use state + request + selected outcome to build a wire-compatible response
```

A path may require multiple fresh sessions when an action consumes state. That is expected. Optimization means avoiding semantically false combinations, not skipping real paths.

Observed sample counts are evidence only and must not be treated automatically as RNG probabilities.
