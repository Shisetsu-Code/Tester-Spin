# GPAS Family Primitives Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans or
> superpowers:subagent-driven-development to implement each task with regression
> tests. Independent tasks have explicit file/function ownership.

**Goal:** Update reusable GPAS primitives and expose measured family coverage.

**Architecture:** Shared source-bound command builders and per-operation server
configuration feed an offline family audit. Historical observations remain
distinct from live authorization and game-level verdicts.

**Tech Stack:** Python 3.11+, pytest, existing GPAS runtime; no new dependency.

**Spec:** `docs/superpowers/specs/2026-10-25-gpas-family-primitives-design.md`

## Global Constraints

- No game/title allowlists or session identifiers in production decisions.
- No captured JavaScript execution, wager replay or changes to historical OKs.
- Existing command and settlement guards remain effective.
- Publish sanitized fixtures and evidence references only.

## Review Focus

- Per-feature overrides must not inherit inappropriate base limits.
- Client source must establish command class and serializer, not mere presence.
- Cross-file fragments require exact connection and request correlation.
- An open prefix or mismatched balance cannot become verified settlement.
- Output paths must not overwrite input captures; reports omit session secrets.

## Task 1: Scoped operation discovery

Files: `providers/playtech/primitives.py` discovery only, `adapter.py`, a scoped
configuration helper if needed, and new scope regression tests.

Interface: `discover_modes(configuration, contract, sources,
configuration_rows=...)`, with the extra parameter optional and keyword-only.

- [ ] Reproduce feature-specific maximum/default mismatch with sanitized rows.
- [ ] Validate scope, cost identity, multiplier domain and disabled modes.
- [ ] Pass raw rows from both live adapter discovery paths.
- [ ] Run new tests and existing GPAS discovery/adapter regressions.

## Task 2: Source-bound command families

Files: `providers/playtech/command_families.py`, contract/builders in
`primitives.py`, continuation construction if needed, and family tests.

- [ ] Obtain and inspect static family source without issuing game commands.
- [ ] Reproduce unsupported accepted command class/serializer with a small fixture.
- [ ] Implement bounded source binding and family-specific serialization.
- [ ] Test ambiguous/missing bindings and unchanged existing families.

## Task 3: Offline audit and CLI

Files: `providers/playtech/family_audit.py`, `cli.py`, `har_learning.py`, tests,
small sanitized fixtures, and user-facing documentation/report.

Interface: `analyze_hars(paths: list[Path]) -> dict`, schema
`tester-spin/playtech-family-audit/v1`, family capabilities and explicit
`certifies_live_ok=false`.

- [ ] Test fragmented/correlated captures, duplicates, malformed/open rounds,
  metadata renaming and secret-free output against real primitives.
- [ ] Implement HAR/ZIP ingestion and family/capability aggregation.
- [ ] Add `tester-spin families playtech ... --output ...` and GPAS manual
  capture diagnostics; test input preservation and no storage/network side effects.
- [ ] Evaluate original archive with baseline and updated primitives.
- [ ] Run suite, independent review, and publish branch/PR with measured results.
