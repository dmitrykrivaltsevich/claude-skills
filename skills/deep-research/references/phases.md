# Phase Reference — Detailed Prompt Patterns

## Contents

1. [Phase 1: Scope & Decompose](#phase-1-scope--decompose)
2. [Phase 2: Broad Sweep](#phase-2-broad-sweep)
3. [Phase 3: Deep Read](#phase-3-deep-read)
4. [Phase 4: Cross-Reference](#phase-4-cross-reference)
5. [Phase 5: Synthesise](#phase-5-synthesise)
6. [Skill Routing Examples](#skill-routing-examples)
7. [State File Schema](#state-file-schema)

---

## Phase 1: Scope & Decompose

**Goal**: Turn the user's request into a structured set of research questions.

**Steps**:
1. Run `discover.py` — get the capability map
2. Run `state.py init --research-id "<slug>" --goal "<user's goal>"`
3. Generate 5–15 sub-questions from the goal
4. Write questions JSON to temp file → `state.py add-questions --file /tmp/questions.json`

**Question quality checklist**:
- [ ] Each question is specific and answerable from a source
- [ ] Questions cover different angles (what, why, who, when, how, compared-to)
- [ ] At least one question targets contradictions or controversies
- [ ] At least one question targets recent developments (past 30 days)

**Example decomposition**:

User: "Research the current state of quantum computing"

Questions:
1. "What are the largest quantum computers by qubit count as of March 2026?"
2. "Which companies have demonstrated quantum advantage for a practical application?"
3. "What are the main quantum error correction approaches being pursued?"
4. "What is the current state of quantum computing funding and investment?"
5. "What are the most promising near-term quantum computing applications?"
6. "What are the main criticisms or skepticism about quantum computing timelines?"
7. "How do trapped-ion vs superconducting vs photonic approaches compare in 2026?"
8. "What quantum computing standards or regulations have been proposed?"

## Phase 2: Broad Sweep

**Goal**: Cast a wide net — find sources for as many questions as possible.

> **NEVER use Agent(), built-in Web Search, or Fetch.** Run `/duckduckgo` scripts directly via `uv run`. Read `/duckduckgo` SKILL.md first to get the correct `${CLAUDE_SKILL_DIR}`.

**Steps per round** (3–5 questions per round):
1. Select unexplored questions
2. For each, choose the best script from the capability map
3. Execute searches via duckduckgo scripts into a discovery artifact using native `--output` when available (NEVER built-in Web Search)
4. Build a smaller working-set artifact from that discovery artifact
5. Write sources JSON for only the shortlisted sources → `state.py add-sources --file /tmp/sources.json`
6. Write facts JSON for only accepted preliminary facts → `state.py add-facts --file /tmp/facts.json`
7. Update question status: `state.py update-question --status partially`

**State/environment pattern per round**:
- Discovery artifact: `/tmp/<research-id>-qN-discovery.json`
- Working-set artifact: `/tmp/<research-id>-qN-working-set.json`
- Research state: `state.py`

The transcript should carry only the artifact paths and a short summary, not the full search payload.

When a later step needs only part of a saved JSON artifact, use `json_query.py` rather than reopening the full file.

**Routing pattern** (read each skill's SKILL.md to get correct `${CLAUDE_SKILL_DIR}` paths):
```
For each question:
  1. Does it need web data? → read /duckduckgo SKILL.md → use its search.py / top_news.py
  2. Does it need internal docs? → read /google-drive SKILL.md → use its search.py
  3. Does it need claim verification? → read /duckduckgo SKILL.md → use its fact_check.py
  4. Does it need trend data? → read /duckduckgo SKILL.md → use its trending.py
  5. Does it need multi-language coverage? → read /duckduckgo SKILL.md → use its translate_search.py
```

**Search strategy**:
- Start with news search for recent topics
- Use text search for technical/evergreen topics
- Use `top_news.py` with specific `--queries` for broad coverage topics
- If initial search returns noise, decompose into more specific queries

## Phase 3: Deep Read

**Goal**: Get full text of the most promising sources and extract detailed facts.

**Source prioritisation** (LLM decides):
1. Wire services and primary sources (direct announcements, press releases)
2. Quality publications with original reporting
3. Technical blogs and documentation
4. Aggregators and secondary coverage (use for leads, not as primary sources)

**Steps**:
1. For each `partially` covered question, pick top 2–3 sources from the latest working-set artifact
2. Download full text using duckduckgo's `download.py <url> --format md --output /tmp/<research-id>/pages/<slug>.md`. **NEVER use built-in Fetch** — it gets 403 errors because it doesn't mimic a browser. `download.py` handles this.
3. Use `page_query.py` to reopen only the relevant heading, chunk, or line range from the downloaded page
4. Read the sliced content
5. Extract facts with confidence levels and source attribution
6. Write facts JSON to temp file → `state.py add-facts --file /tmp/facts.json`
7. If the article mentions something unexpected, generate a new question

The downloaded page directory is part of the research environment. Reopen the specific page slice you need with `page_query.py`; do not keep whole articles live in prompt context once facts were extracted.

**Confidence levels**:
- `high`: Multiple independent quality sources agree; or official primary source
- `medium`: Single quality source; or multiple lower-quality sources agree
- `low`: Single blog/social media post; or claim is hedged ("reportedly", "sources say")

## Phase 4: Cross-Reference

**Goal**: Validate findings, resolve contradictions, fill gaps.

**Steps**:
1. Run `state.py export` — review all facts
2. Reopen only the smallest relevant working-set or page artifacts for the theme under review using `json_query.py` or `page_query.py`
3. Group facts by theme
4. For each theme, check:
   - Do sources agree? → Mark as high confidence
   - Do sources disagree? → Search for resolution, or flag as contested
   - Is there only one source? → Search for corroboration
5. For remaining `unexplored` questions: try alternative search strategies
6. Record any new facts or updated confidence levels

Use `json_query.py` on exported state files or working-set artifacts when you only need one theme, one question subset, or one source subset.

**Contradiction resolution**:
- Search for the specific disagreement point
- Check publication dates — newer data may supersede older
- Check source authority — primary source > secondary > opinion
- If unresolvable, record both claims with a note about the disagreement

## Phase 5: Synthesise

**Goal**: Produce the final research report.

**Steps**:
1. Run `state.py export` for the complete state
2. Run `state.py status` for coverage summary
3. Structure the report:

```markdown
# Research Report: <goal>

## Executive Summary
2–3 paragraph overview of key findings. Include inline citations [1], [2] for every claim.

## Key Findings
### Finding 1: <headline>
<details with inline citations, e.g. "X increased by 40% [1] while Y declined [2, 3].">
**Confidence**: high | medium | low

### Finding 2: ...

## Open Questions
- Questions that remain unexplored or partially covered
- Areas where sources significantly disagree

## Methodology
- N sources consulted across M skills
- Research phases completed: scope → sweep → deep-read → cross-reference

## Sources
[1] Author (if known). "Title". URL. Accessed YYYY-MM-DD.
[2] Author. "Title". URL. Accessed YYYY-MM-DD.
[3] ...
```

**Citation rules**:
- Every claim, statistic, or factual statement in the report MUST have at least one `[N]` citation
- Use the source IDs from state.py to build the numbered list — assign `[1]`, `[2]`, etc. in order of first appearance in the text
- When multiple sources support the same claim, list all: `[2, 5]`
- The Sources section MUST be numbered, not bulleted — each `[N]` in the text maps to exactly one entry

---

## Skill Routing Examples

Read each skill's SKILL.md before running its scripts — each skill has its own `${CLAUDE_SKILL_DIR}`.

| Research need | Skill to read | Script | Flags |
|---|---|---|---|
| Recent news on topic | `/duckduckgo` | `search.py news` | `--timelimit w` |
| Comprehensive news sweep | `/duckduckgo` | `top_news.py` | `--groups tech science` |
| Full article text | `/duckduckgo` | `download.py` | `--format md` |
| Claim verification | `/duckduckgo` | `fact_check.py` | |
| Trending topics | `/duckduckgo` | `trending.py` | `--discover` or `--topics` |
| Multi-language search | `/duckduckgo` | `translate_search.py` | region:query pairs |
| Topic monitoring | `/duckduckgo` | `monitor.py` | |
| Internal documents | `/google-drive` | `search.py` | `--query "..."` |
| File content | `/google-drive` | `download.py` | `--file-id "..."` |

---

## State File Schema

```json
{
  "research_id": "quantum-computing-2026",
  "goal": "Understand the current state of quantum computing",
  "phase": "cross-reference",
  "questions": [
    {"text": "What are the largest quantum computers?", "status": "covered"},
    {"text": "Who demonstrated quantum advantage?", "status": "partially"},
    {"text": "What are the main error correction approaches?", "status": "unexplored"}
  ],
  "sources": [
    {"id": "s1", "url": "https://...", "title": "IBM's 2026 Roadmap", "skill": "duckduckgo"},
    {"id": "s2", "url": "https://...", "title": "Nature: Quantum Error Correction", "skill": "duckduckgo"}
  ],
  "facts": [
    {"id": "f1", "claim": "IBM reached 1386 qubits in Feb 2026", "source_ids": ["s1"], "confidence": "high"},
    {"id": "f2", "claim": "Google claims quantum advantage for drug discovery", "source_ids": ["s2"], "confidence": "medium"}
  ],
  "created_at": "2026-03-11T10:00:00+00:00",
  "updated_at": "2026-03-11T12:30:00+00:00"
}
```

Question statuses: `unexplored` → `partially` → `covered`

Phases: `scope` → `sweep` → `deep-read` → `cross-reference` → `synthesise`
