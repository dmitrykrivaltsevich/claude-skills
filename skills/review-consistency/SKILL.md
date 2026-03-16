---
name: review-consistency
description: Reviews internal consistency of code, documents, diffs, or any structured content. Catches contradictions, forgotten propagation, semantic drift, stale references, implausible claims, argument incoherence, convention breaks, and incomplete changes. Use when the user asks to review consistency, check for contradictions, verify a change is complete, audit docs vs. code alignment, or validate logical coherence of any material.
user-invocable: true
---

# Review Consistency Skill

## Contents

1. [Purpose](#purpose)
2. [Inconsistency Taxonomy](#inconsistency-taxonomy)
3. [Review Modes](#review-modes)
4. [Workflow](#workflow)
5. [Output Format](#output-format)
6. [Severity Levels](#severity-levels)
7. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)

## Purpose

This skill is pure LLM reasoning — no scripts. The LLM reads the material, builds an internal model of claims/contracts/conventions, then systematically checks that model for contradictions and gaps.

The core insight: inconsistency is **relational** — it exists between two or more statements, not within one. The methodology is always: extract claims, then compare them pairwise or against a global invariant.

## Inconsistency Taxonomy

Check for these eight classes, in order from most to least severe:

### 1. Internal Contradiction

Two statements that cannot both be true.

- Code: function signature says it returns `string`, implementation returns `number`
- Docs: README says "supports Node 18+", package.json has `"engines": {"node": ">=20"}`
- Config: env var documented as `API_URL`, code reads `API_ENDPOINT`

### 2. Forgotten Propagation

A change was made in one place but not carried through to all dependent sites.

- Renamed a function but callers still use old name
- Changed a DB column name in migration but not in queries
- Updated an API response shape in backend but not in frontend types
- Changed a constant value in one file but not where it's duplicated

### 3. Semantic Drift

Same concept referred to by different names, or same name used for different concepts.

- Variable called `user` in one module, `account` in another, both mean the same entity
- `timeout` means "connection timeout" in one config, "request timeout" in another
- Doc section calls it "workspace", code calls it "project", API calls it "repository"

### 4. Stale References

Pointers to things that moved, were renamed, or no longer exist.

- Import path references a module that was moved
- Doc links to a section heading that was reworded
- Comment references line numbers that shifted
- Error message mentions a flag that was removed

### 5. Implausibility

Claims that cannot be true even in principle — not contradicting another statement, but contradicting reality or logic.

- "This O(n!) algorithm runs in under 1ms for n=1000"
- "The 8-bit field stores values up to 1024"
- "This single-threaded function processes 10M requests per second"
- "Released in 2019" for a technology that launched in 2022

### 6. Argument Incoherence

Premises lead one direction, conclusion goes another. Reasoning doesn't follow.

- Doc motivates a design with "simplicity", then describes a 7-layer abstraction
- Comment says "fast path optimization", code adds three extra branches
- Architecture doc argues for microservices, then constrains all services to share one DB

### 7. Convention Break

An established pattern is followed consistently except in some places.

- All error handlers use `try/catch` except one that uses `.catch()`
- All API routes return `{data, error}` except one that returns `{result, message}`
- All files use camelCase except two that use snake_case
- All tests mock the DB layer except one that hits a real database

### 8. Incomplete Change

A diff that touches some sites but visibly misses others that need the same treatment.

- Added a new enum value but didn't add its case to the switch statement
- Added a field to a struct but didn't update the serializer
- Changed validation rules for creation but not for update
- Added a new permission but didn't add it to the permission check middleware

## Review Modes

### Change Review (Diff)

Given a diff or set of changed files:

1. **Read the full diff** — understand every hunk
2. **For each change, ask**: what other places in the codebase depend on, reference, or mirror this?
3. **Read those dependent places** — verify they were also updated or still hold
4. **Check the diff against itself** — do the changes across files tell a coherent story?

### Document Review

Given one or more documents:

1. **Extract all factual claims** — each statement that asserts something concrete
2. **Extract all prescriptive claims** — each statement that says what should/must/will happen
3. **Compare every pair** — can both be true simultaneously?
4. **Check against general knowledge** — any implausible claims?
5. **Check internal terminology** — is the same term used consistently?

### Cross-File Review

Given a set of related files (e.g., a module, a feature):

1. **Identify the contracts** — interfaces, types, schemas, configs that multiple files depend on
2. **For each contract, check all consumers** — do they all agree on shape, naming, semantics?
3. **Check conventions** — what patterns repeat? where do they break?
4. **Check data flow** — does the output shape of A match the expected input shape of B?

### Code-Docs Alignment

Given code and its documentation:

1. **Extract the doc's claims about behavior** — parameters, return values, side effects, constraints
2. **Read the actual implementation** — what does the code really do?
3. **Diff the two** — where do docs promise something code doesn't deliver, or vice versa?
4. **Check examples** — would the documented examples actually work against the current code?

## Workflow

```
1. User provides material (files, diff, documents, URLs) and optionally a review mode
2. LLM selects review mode (or defaults based on material type):
   - diff → Change Review
   - single doc → Document Review
   - multiple related files → Cross-File Review
   - code + docs → Code-Docs Alignment
   - mixed → combine modes as needed
3. LLM reads ALL material thoroughly — no skimming
4. LLM extracts claims/contracts/conventions into a mental model
5. LLM systematically checks the 8 inconsistency classes
6. LLM reports findings using the output format below
7. If findings suggest more files need reading, read them and repeat from step 4
```

**Iterative deepening**: if the first pass reveals that a change touched module A, but module B also depends on the same interface — read module B and check it too. Don't stop at the provided material if there's reason to believe inconsistency extends further.

## Output Format

Report each finding as:

```
### [SEVERITY] Inconsistency Class — Short title

**Where**: file(s) and location(s)
**What**: describe the two (or more) things that conflict
**Why it matters**: what could go wrong
**Suggestion**: how to resolve (if obvious)
```

Group findings by severity. Lead with a summary count:

```
## Consistency Review Summary

- X critical findings
- Y major findings
- Z minor findings
- W nits

(or "No inconsistencies found" — but double-check before saying this)
```

## Severity Levels

| Severity | Meaning | Examples |
|----------|---------|---------|
| **Critical** | Will cause runtime failure, data loss, or security vulnerability | Type mismatch, missing propagation that breaks callers, contradictory access control rules |
| **Major** | Will cause confusion, wrong behavior in edge cases, or maintenance burden | Semantic drift across modules, stale references that mislead, implausible claims in docs |
| **Minor** | Cosmetic or low-impact but still technically inconsistent | Convention breaks, slightly outdated comments, minor terminology drift |
| **Nit** | Stylistic inconsistency, not functionally wrong | Formatting differences, comment style variations |

## Anti-Patterns to Avoid

- **Do not invent problems.** Only report actual inconsistencies you can point to concretely. "This might be inconsistent" with no evidence is not a finding.
- **Do not report style preferences as inconsistencies.** Unless the codebase has an established convention that is broken, stylistic variation is not an inconsistency.
- **Do not overwhelm with nits.** If there are many nits of the same kind, report the pattern once with examples, not each instance separately.
- **Do not skip reading.** Never assess consistency of material you haven't fully read. If you can't read it all, say so.
- **Do not confuse "different" with "inconsistent".** Two modules can use different approaches for good reasons. Inconsistency means they *should* agree but don't.
- **Do not report known trade-offs as inconsistencies.** If the code explicitly documents why it deviates from a convention, that's intentional, not inconsistent.
