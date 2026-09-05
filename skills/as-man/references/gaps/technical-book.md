# Gaps — technical book

Applies to: textbooks and professional technical books, whole or read chapter by chapter.

## Expected coverage

| Probe | What a reader needs |
|---|---|
| Edition drift | What changed since this edition, and which advice is now wrong. Books age silently. |
| Era assumptions | Hardware, scale, cost and tooling assumed by the author, and whether they still hold. |
| Prerequisites | What the chapter assumes you read first. A chapter read alone often silently depends on an earlier one. |
| Scope boundary | What the book deliberately leaves to other books, and where to go for it. |
| Contested material | Where the field disagrees with the author, and who disagrees. |
| Exercises | Whether a caveat is hidden in an exercise rather than stated in the text. |
| Worked examples | Whether the examples are simplified past the point where the technique still works. |
| Empirical grounding | Which claims rest on evidence and which on the author's experience. |
| Practitioner reality | What the book teaches as standard that industry does not actually do. |

## Genre traps

- **Authoritative tone hides age.** A confident chapter on storage from 2012 assumes spinning disks. The advice is internally coherent and externally obsolete.
- **The canonical text defines the vocabulary.** Terms the book coined may not mean the same thing elsewhere; a reader quoting them will be misunderstood.
- **Chapter isolation.** When reading one chapter, the missing context from earlier chapters is a genuine gap for this reader, even though the book covers it.
- **Second-system advice.** Books often describe the ideal design and omit the migration cost from what the reader already has.

For a chapter read on its own, always probe prerequisites first: it is the gap most likely to damage the reader immediately.

## Example

```
GAP 1 - Latency figures assume rotational disks

Kind:         stale
Materiality:  high
Missing:      The chapter's seek-time argument assumes a rotational disk. On
              solid-state storage the random-access penalty it is built on is
              roughly two orders of magnitude smaller.
Effect:       A reader designs around sequential access for a workload where
              random access is now acceptable, and pays in complexity.
Evidence:     [unverified - model knowledge, confirm before acting]
```
