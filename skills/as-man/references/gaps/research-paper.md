# Gaps — research paper

Applies to: conference and journal papers, preprints, surveys, benchmark studies.

## Expected coverage

| Probe | What a reader needs |
|---|---|
| Baselines | Which obvious competitor was not run, and would it have won? A missing baseline is the most common material omission in this genre. |
| Tuning budget | How much search went into the proposed method compared to the baselines? An unequal budget makes the comparison meaningless. |
| Variance | Seeds, runs, confidence intervals. A single-run result with a 0.4-point margin says nothing. |
| Effect size | Is the improvement large enough to matter, separately from being significant? |
| Data provenance | Licence, collection method, and whether the test set could be in the training data. |
| Compute | What it cost to train and to run. A method that needs 100 times the compute is not a drop-in replacement. |
| Negative results | Which configurations were tried and dropped. |
| Failure modes | Where the method breaks, not only where it wins. |
| Generalisation | Which of the claims survive outside the datasets tested. |
| Funding and affiliation | Who paid, and whether the result favours them. |
| Reproduction | Is there code, and has anyone independently reproduced it? |
| Prior art | Work that made a similar claim earlier, especially outside the paper's own community. |

## Genre traps

- **The abstract overstates the paper.** Compare the abstract's claim with what the experiments actually support. The difference is often the single most material gap.
- **Benchmark saturation.** A gain on a benchmark near its ceiling can be noise or contamination.
- **Cherry-picked qualitative examples.** Figures showing successes with no matching failure sample.
- **Metric substitution.** The paper measures a proxy and concludes about the thing itself.
- **"Related work" as a moat.** Omitted comparisons are often the closest competitors.

For a survey, the gap is usually selection: which line of work was excluded, and does the exclusion favour the authors' own position? For a benchmark paper, ask what the benchmark cannot measure, and who is now optimising against it.

## Example

```
GAP 1 - No variance is reported across seeds

Kind:         omission
Materiality:  high
Missing:      Results come from a single run per configuration; the reported
              gain of 0.4 points is smaller than the seed variance typical for
              this benchmark.
Effect:       A reader treats the ranking as established and adopts a method
              that may not be better than the baseline.
Evidence:     [unverified - model knowledge, confirm before acting]
```
