# Gaps — product, API and tool documentation

Applies to: official product docs, API references, READMEs, tool manuals, getting-started guides.

## Expected coverage

| Probe | What a reader needs |
|---|---|
| Failure modes | What happens when it fails, what the error looks like, and what to do. |
| Limits | Rate limits, size limits, quotas, timeouts, and behaviour at the limit. |
| Cost | Pricing, and which operations are unexpectedly expensive. |
| Version skew | Which versions this applies to, and behaviour differences between them. |
| Migration and rollback | Upgrade path, breaking changes, and how to go back. |
| Security | Authentication, permission scope, secret handling, and what is exposed by default. |
| Data handling | What is retained, where, and for how long. |
| Concurrency | Behaviour under parallel use: idempotency, retries, and race conditions. |
| Production readiness | What the quickstart omits that a production deployment needs. |
| Alternatives | When not to use this, and what to use instead. |
| Deprecation | What is being removed and on what schedule. |
| Operational reality | Observability, backup, and how to debug it when it misbehaves. |

## Genre traps

- **The happy path is the whole document.** Quickstarts optimise for a working example in five minutes and omit everything that makes it safe.
- **The vendor writes the docs.** "When not to use this" is structurally absent.
- **Defaults are not stated.** A default that is convenient for demonstration is often wrong for production, especially in security settings.
- **Errors are listed without meaning.** A table of codes with no cause and no remedy.
- **Documentation drifts from the implementation.** Check whether the version documented is the version shipped.
- **Retry advice without idempotency guarantees.** Guidance to retry, with no statement of whether retrying is safe.

## Example

```
GAP 1 - Rate limits are not documented

Kind:         omission
Materiality:  high
Missing:      The reference does not state the request limit, the window it
              applies over, or the response returned when it is exceeded.
Effect:       A reader builds a client without backoff and discovers the limit
              in production, under load.
Evidence:     [unverified - model knowledge, confirm before acting]
```
