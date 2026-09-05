# Gaps — incident report and post-mortem

Applies to: public incident summaries, outage reports, internal post-mortems.

## Expected coverage

| Probe | What a reader needs |
|---|---|
| Contributing factors | What else had to be true. A single named root cause is almost always a simplification. |
| Detection delay | Time from onset to detection, and why monitoring did not catch it sooner. |
| Blast radius | Effects beyond the named service, including dependent customers and delayed effects. |
| Duration honesty | Whether the stated window covers full recovery or only the primary fault. |
| Prior incidents | Whether something similar happened before, and what was promised then. |
| Undisclosed impact | Data loss, corruption, or security exposure, which are often described in softer language than availability. |
| Action items | Whether remedies are specific and owned, or generic commitments. |
| Why the safeguard failed | Existing protections that did not fire, and why. |
| Recovery cost | What manual work restoration required, and whether it is repeatable. |

## Genre traps

- **Legal and commercial review shapes the text.** A public report is written to be defensible. Read the passive voice: "an incorrect configuration was applied" hides who applied it and how it passed review.
- **Root cause as a stopping point.** Naming one cause ends the analysis at the most convenient place.
- **Timeline gaps.** Long unexplained intervals in the timeline usually mark the part nobody wants to describe.
- **Impact stated in the operator's terms.** "Elevated error rates" can mean a total outage for a subset of customers.

## Example

```
GAP 2 - Detection delay is not explained

Kind:         omission
Materiality:  high
Missing:      The timeline shows 47 minutes between onset and detection, but
              the report does not say which alert eventually fired or why the
              existing monitoring did not.
Effect:       A reader adopting the same monitoring approach inherits the same
              blind spot and cannot tell which signal to add.
Evidence:     [unverified - model knowledge, confirm before acting]
```
