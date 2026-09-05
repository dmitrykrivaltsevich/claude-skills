# Gaps — design document, RFC, architecture decision record

Applies to: technical design documents, internal RFCs, ADRs, proposals that ask for a decision.

## Expected coverage

| Probe | What a reader needs |
|---|---|
| Rejected alternatives | What else was considered and the specific reason each was dropped. A design with no rejected alternatives was not designed, it was assumed. |
| Do nothing | Whether the cost of changing nothing was assessed. Often the strongest option and the least often written down. |
| Rollback | How to undo this after it ships, and the point past which undoing becomes impossible. |
| Migration | How the system gets from the current state to the proposed one while serving traffic, and how long it runs in both states. |
| Failure modes | What breaks when each new component is unavailable, and what the degraded behaviour is. |
| Success criteria | The measurable condition that makes this a success, decided before it ships. |
| Ownership | Who operates this after launch, and whether that team agreed. |
| Cost | Infrastructure spend, engineering time, and ongoing maintenance. |
| Blast radius | Which other teams and systems are affected, and whether they were consulted. |
| Security and privacy | New data paths, new trust boundaries, new retention. |
| Interim state | What is true during the migration, which is often worse than either the before or the after. |
| Deadline pressure | Whether the design is shaped by a date rather than by the problem. |

## Genre traps

- **The document is written to be approved.** Its purpose is to secure a decision, so risks are compressed and alternatives are presented weakly. Read rejected alternatives for strawmen: an option dismissed in one clause was probably not evaluated.
- **Reversibility is assumed and never stated.** A design that writes a new schema, changes an external contract, or migrates data is frequently irreversible in practice while reading as reversible.
- **The interim state has no owner.** Both end states are described; the months in between are not.
- **Estimates without a unit of confidence.** "Two weeks" with no statement of what it excludes.
- **Second-order effects on other teams.** The document scopes itself to one team's surface and omits who else must change.

For an ADR specifically, probe the consequences section hardest: ADRs are strong at recording what was decided and weak at recording what the decision costs later.

## Example

```
GAP 1 - No rollback path once the migration writes to the new schema

Kind:         omission
Materiality:  high
Missing:      The design describes forward migration but not how to return to
              the previous schema after dual writes begin. From that point the
              old schema is missing rows written to the new one.
Effect:       A reviewer approves the design believing the change is
              reversible, and the team discovers it is not during an incident.
Evidence:     [unverified - model knowledge, confirm before acting]
```
