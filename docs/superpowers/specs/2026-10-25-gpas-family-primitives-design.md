# GPAS primitives and family evaluation

## Intent

Update reusable protocol primitives and measure coverage by family, as requested,
instead of adding game-specific exceptions. The existing HardFire archive is
the observed regression corpus: 76 HAR files, 175 correlated operations, 76
rounds, 74 closed and reconciled rounds, and two unfinished captured prefixes.

## Approach

Use command class and wire dialect to identify families. Resolve monetary
configuration for each operation's complete server context. Keep source-bound
live contracts separate from historical wire observations, then evaluate the
same builders, continuation logic and ledger over captured messages.

The user selected family-level work. A title allowlist would not generalize;
blindly replaying captured requests would reuse session state and would not
establish a current client contract. Neither is part of this design.

## Boundaries

- Extend the existing Python 3.11+ implementation; add no runtime dependency.
- Preserve the existing API for callers that provide resolved configuration.
- Production GPAS discovery must supply raw configuration rows, including after
  reopening a demo, so each mode uses its own limits and multiplier domain.
- Bind new command families only to observed static client constructors and
  serializers; an identifier appearing somewhere in source is insufficient.
- Identify a family without game codes, display titles, prices or captured UUIDs.
- Keep uncertain/unsupported operations pending and preserve settlement checks.
- Analyze HAR/ZIP inputs offline; never evaluate captured JavaScript or replay
  captured tokens, requests or sessions.
- Reports distinguish builder compatibility, observed continuations, settlement,
  missing source evidence and current live execution. They do not change SQLite
  results or certify a whole game from one historical round.
- Publish only small sanitized fixtures and derived reports, never raw HARs.

## Components

1. Scoped operation discovery: resolve and validate limits, factors and cost
   identity for each betType/featureType context.
2. Command contracts: family-specific source bindings and shared builders where
   source evidence establishes the wire format.
3. Offline family audit: merge exact connections across captures, correlate
   GameCommand messages, exercise primitives and group results by family.
4. CLI and manual capture diagnostics: expose the audit without opening a browser,
   requesting a wager, starting a learner or mutating game verdicts.

## Acceptance

Regression tests must fail on the original implementation, demonstrate generic
behavior under renamed game/UUID metadata, and cover malformed context,
unbound source, correlation ambiguity, missing closure and inconsistent balance.
Run the same offline audit against the preserved baseline and updated core.
Report changes by capability and family, with explicit evidence limits.
