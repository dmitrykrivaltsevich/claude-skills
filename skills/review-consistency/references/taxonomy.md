# Inconsistency Taxonomy

Check for these eight classes, in order from most to least severe:

## 1. Internal Contradiction

Two statements that cannot both be true.

- Code: function signature says it returns `string`, implementation returns `number`
- Docs: README says "supports Node 18+", package.json has `"engines": {"node": ">=20"}`
- Config: env var documented as `API_URL`, code reads `API_ENDPOINT`

## 2. Forgotten Propagation

A change was made in one place but not carried through to all dependent sites.

- Renamed a function but callers still use old name
- Changed a DB column name in migration but not in queries
- Updated an API response shape in backend but not in frontend types
- Changed a constant value in one file but not where it's duplicated

## 3. Semantic Drift

Same concept referred to by different names, or same name used for different concepts.

- Variable called `user` in one module, `account` in another, both mean the same entity
- `timeout` means "connection timeout" in one config, "request timeout" in another
- Doc section calls it "workspace", code calls it "project", API calls it "repository"

## 4. Stale References

Pointers to things that moved, were renamed, or no longer exist.

- Import path references a module that was moved
- Doc links to a section heading that was reworded
- Comment references line numbers that shifted
- Error message mentions a flag that was removed

## 5. Implausibility

Claims that cannot be true even in principle — not contradicting another statement, but contradicting reality or logic.

- "This O(n!) algorithm runs in under 1ms for n=1000"
- "The 8-bit field stores values up to 1024"
- "This single-threaded function processes 10M requests per second"
- "Released in 2019" for a technology that launched in 2022

## 6. Argument Incoherence

Premises lead one direction, conclusion goes another. Reasoning doesn't follow.

- Doc motivates a design with "simplicity", then describes a 7-layer abstraction
- Comment says "fast path optimization", code adds three extra branches
- Architecture doc argues for microservices, then constrains all services to share one DB

## 7. Convention Break

An established pattern is followed consistently except in some places.

- All error handlers use `try/catch` except one that uses `.catch()`
- All API routes return `{data, error}` except one that returns `{result, message}`
- All files use camelCase except two that use snake_case
- All tests mock the DB layer except one that hits a real database

## 8. Incomplete Change

A diff that touches some sites but visibly misses others that need the same treatment.

- Added a new enum value but didn't add its case to the switch statement
- Added a field to a struct but didn't update the serializer
- Changed validation rules for creation but not for update
- Added a new permission but didn't add it to the permission check middleware

## Claim Categories

When extracting claims during the extract phase, classify each as:

| Category | Meaning | Example |
|---|---|---|
| **contract** | Explicit interface promise — types, signatures, return values, schemas | "function `foo(x: int) -> str`" |
| **convention** | Implicit project pattern — naming, structure, error handling style | "all routes return `{data, error}` shape" |
| **assertion** | Factual claim about behavior, performance, or state | "cache invalidates after 5 minutes" |
| **reference** | Pointer to another location — imports, links, file paths | "imports `utils.validate` from `src/utils.py`" |
