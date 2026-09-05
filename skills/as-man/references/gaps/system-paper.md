# Gaps — industry system paper

Applies to: engineering papers and blog posts describing a system a company built and runs.

## Expected coverage

| Probe | What a reader needs |
|---|---|
| Breaking scale | The load or size at which the design stops working. Papers give the scale it reached, rarely the scale it failed at. |
| Cost | Money, machines, and the size of the team that operates it. |
| Operational burden | On-call load, manual interventions, and what it takes to run in steady state. |
| The boring alternative | Why the obvious off-the-shelf option was rejected. Often it was not evaluated. |
| Unpublished failures | Earlier versions that were abandoned, and why. |
| Preconditions | Company-specific infrastructure the design silently depends on. |
| Workload shape | The traffic pattern it was tuned for, and what happens under a different one. |
| Migration | What it took to get from the previous system to this one. |
| Current status | Whether the company still runs it. Many celebrated systems were replaced. |
| Selection bias | Systems that failed do not get papers written about them. |

## Genre traps

- **Publication is recruitment and positioning.** The incentive is to present a solved problem. Anything unresolved is likely absent rather than absent-because-solved.
- **Scale as authority.** "Serves ten million requests per second" does not establish that the design suits a reader serving ten thousand.
- **Missing denominators.** Improvements given as percentages with no absolute baseline.
- **Infrastructure assumed.** The design may depend on an internal service that has no external equivalent.

## Example

```
GAP 1 - The operational cost of the design is never stated

Kind:         omission
Materiality:  high
Missing:      The paper reports throughput and latency but not the team size
              or on-call load required to operate the system.
Effect:       A smaller organisation copies the architecture without the staff
              to run it, and inherits an operational burden it cannot carry.
Evidence:     [unverified - model knowledge, confirm before acting]
```
