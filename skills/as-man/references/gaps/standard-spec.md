# Gaps — standard, specification, body of knowledge

Applies to: protocol specifications, formal standards, bodies of knowledge, conformance documents.

## Expected coverage

| Probe | What a reader needs |
|---|---|
| Requirement strength | Which parts are mandatory, which recommended, which optional. Readers routinely treat a recommendation as a requirement. |
| Deliberate exclusions | What the standard states is out of scope, and where that responsibility falls instead. |
| Implementation divergence | How real implementations differ from the text. The gap between specification and practice is usually where the reader gets hurt. |
| Versioning | Which version this is, what changed, and how versions negotiate. |
| Deprecation | What is retained only for compatibility and should not be used in new work. |
| Undefined behaviour | What the specification leaves unspecified, and what implementations do there. |
| Conformance testing | Whether a test suite exists and what conformance actually certifies. |
| Security considerations | Threats the design does not address. |
| Adoption | Whether anyone implements this, and which parts are implemented in practice. |
| Governance | Who controls the standard and how changes are made. |

## Genre traps

- **Normative language is load-bearing.** `MUST`, `SHOULD` and `MAY` are precise terms. A summary that renders them all as "needs to" destroys the document's meaning. Preserve them exactly.
- **The specification describes the ideal.** Interoperability problems live in the difference between the text and the deployed population.
- **A body of knowledge describes consensus, not practice.** It records what the field agrees it should do.
- **Optional features fragment the ecosystem.** A large optional surface means two conformant implementations may not interoperate.

## Example

```
GAP 1 - The document does not say which requirements are optional

Kind:         understated
Materiality:  high
Missing:      Roughly a third of the described behaviour is marked SHOULD
              rather than MUST, so a conformant implementation may omit it.
Effect:       A reader builds against the full description and finds that a
              conformant peer does not implement the parts they depend on.
Evidence:     [unverified - model knowledge, confirm before acting]
```
