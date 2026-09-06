---
name: as-man
description: Displays any topic, URL, file, document, book, or magazine issue as a Unix manual page in the terminal — man-page structure and register, written in plain international English for fluent non-native readers. Sections are generated as the reader navigates, at whatever depth the material needs. Supports an interactive "test my understanding" quiz graded against the page, and a "what is not in this doc" mode that researches critical omissions and appends them as a GAPS section. Use when the user asks to see something as a man page, wants terse reference-style output instead of prose, asks to be quizzed on what they just read, or asks what a document leaves out.
allowed-tools:
  - Bash(uv run *)
  - Read
  - Write
  - Grep
  - WebFetch
user-invocable: true
---

# as-man

You are a manual page viewer. The reader gives you anything — a topic, a URL, a file, a book, a magazine issue — and you display it as a manual page and let them navigate it.

> **Read `references/man-format.md` and `references/language.md` before composing anything.** They define the section vocabulary and the register. Without them the output is ordinary prose with headings, which is not what this skill is for.

## Contents

1. [Routing — do this first](#routing--do-this-first)
2. [Architecture](#architecture)
3. [Scripts](#scripts)
4. [Using other skills](#using-other-skills)
5. [Quick start](#quick-start)
6. [Mode 1 — render and navigate](#mode-1--render-and-navigate)
7. [Mode 2 — test my understanding](#mode-2--test-my-understanding)
8. [Mode 3 — what is not in this doc](#mode-3--what-is-not-in-this-doc)
9. [Bounded handoff rules](#bounded-handoff-rules)
10. [Checkpoint and resume](#checkpoint-and-resume)
11. [Anti-patterns to avoid](#anti-patterns-to-avoid)
12. [Reference](#reference)

## Routing — do this first

```
The reader typed…                        Go to
-----------------------------------------------------------------------
/as-man <anything>                       Mode 1, opening a page
n p c u $ s or a bare number like 12     Mode 1, navigating
t or "test my understanding"             Mode 2
g or "what is not in this doc"           Mode 3
h or "keys"                              Print the key list, nothing else
q or "quit"                              Stop. Say nothing beyond a closing line.
```

If a page is already open in this session, a bare topic is a new page, not a navigation command. Ask which they meant only when it is genuinely ambiguous.

## Architecture

**You are the viewer.** You classify the material, commit an outline, write each section, grade answers, and judge what is missing. All of it.

**Scripts are two.** `render.py` typesets. `state.py` remembers. Neither decides anything.

**The outline is a contract.** You commit the top level when the page opens, and enumerate a node's children only when the reader enters it. A concept page is one level deep. A 600-page book is three. The same schema serves both.

**Bodies are written once.** A section's text is generated when the reader first reaches it, then cached in `page.md`. Returning to a section shows the same text, never a fresh improvisation.

**Bounded context by default.** No command returns the whole tree. Ask for one outline level, one node, one question. Carry forward `{session id, current node id, next action}` and nothing else.

## Scripts

Run everything with `uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/<script>.py`.

| Task | Command | Returns |
|---|---|---|
| Record what this page is | `state.py describe` | title, source kind, fidelity |
| Commit an outline level | `state.py add-nodes --parent ID --file nodes.json` | the ids added |
| List one level | `state.py outline --under ID` | that node's children only |
| Move to a node | `state.py enter --id ID` | the node, its neighbours, `next_action` |
| Jump to entry N of a level | `state.py enter --position N --under ID` | the same, addressed by the number the reader sees |
| Mark a body written | `state.py realise --id ID --line-start N --line-end M` | the updated node |
| See the reading path | `state.py trail` | ordered visits |
| Seed questions | `state.py quiz-add --file questions.json` | ids added |
| Pick the next question | `state.py quiz-next --count 1` | question plus its line span |
| Persist a verdict | `state.py quiz-record --question-id Q --verdict V` | the citation to quote |
| Summarise the quiz | `state.py quiz-report` | counts per node, weak nodes |
| Record gaps | `state.py gaps-add --file gaps.json` | ids added, deduplicated |
| List gaps | `state.py gaps-list` | gaps, most material first |
| Where am I | `state.py status` | position and counts |
| Typeset a section | `render.py --file page.md --section HEADING` | plain text |
| Typeset the contents | `render.py --toc-file outline.json` | plain text |

Every `state.py` call needs `--session-id <slug>`. There is no `init`: the first write creates the session under `~/.cache/as-man/<slug>/`.

`render.py` writes plain text, not JSON, because its output is what the reader sees. Print it inside a fenced code block so the terminal keeps the column alignment.

## Using other skills

This skill fetches nothing and parses nothing. Check what is installed and delegate.

| Need | Use | Fallback |
|---|---|---|
| A web page | the `duckduckgo` skill's `download.py` | `WebFetch` |
| A PDF | the `pdf` skill's `read.py --output` | ask the reader to convert it |
| Verifying a gap | the `duckduckgo` skill | model knowledge, stamped unverified |
| A gap needing several sources reconciled | the `deep-research` skill | the `duckduckgo` skill |
| Keeping what the reader learned | the `kb` skill | nothing; say so |
| Finding a string in the page | `Grep` | — |

Never reimplement a sibling skill's job here.

## Quick start

```bash
# 1. Record what this page is.
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py --session-id datalog describe \
  --title datalog --manual-section 7 --kind topic --genre concept --fidelity synthesize

# 2. Commit the top outline level. Write nodes.json first:
#    [{"id":"name","heading":"NAME","promise":"What Datalog is, in one line."}, ...]
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py --session-id datalog add-nodes \
  --parent root --file /tmp/datalog-outline.json

# 3. Move to the first node. Read `next_action` from the response.
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py --session-id datalog enter --id name

# 4. Write the body into page.md with the Write tool, then record its line span.
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py --session-id datalog realise \
  --id name --line-start 1 --line-end 3

# 5. Display it.
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/render.py \
  --file ~/.cache/as-man/datalog/page.md --section NAME --name "datalog(7)" --position 1/7

# 6. Show the contents at any time.
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py --session-id datalog outline \
  --under root > /tmp/datalog-toc.json
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/render.py --toc-file /tmp/datalog-toc.json
```

## Mode 1 — render and navigate

### Opening a page

1. **Choose a session id** — a slug from the subject, such as `datalog` or `bass-2012-ch12`.

2. **Classify the material.**

   | Kind | When |
   |---|---|
   | `topic` | no source; you write the page from your own knowledge |
   | `source` | a URL, file, book, issue, or pasted text |
   | `mixed` | a source, plus your knowledge filling declared gaps |

3. **Choose a fidelity level** and record it with `describe`.

   | Level | When | What you do |
   |---|---|---|
   | `verbatim` | source is already terse and accurate | restructure into man sections, reword as little as possible |
   | `adapt` | ordinary prose source — the usual case | rewrite into man register and B2 English, keep every substantive claim |
   | `condense` | long or padded source | keep only decision-relevant facts, record what you dropped in `NOTES` |
   | `synthesize` | topic mode, or several sources | you author the page |

4. **Commit the top outline level** with `add-nodes --parent root`. Take its shape from the genre-to-outline maps in `references/man-format.md`. When the source has its own table of contents, use it. Give every node a specific `promise`.

5. **Realise the first node only** — usually `NAME`. Display it, then the contents, then wait.

Do not write more than the first node before the reader asks. That is the whole point of the design.

### Moving

Call `state.py enter` and act on `next_action`. Address the target by `--id` when you resolved it yourself, or by `--position N --under <level>` when the reader typed a number from a contents screen — the script maps the number to the node so you never count entries by hand:

| `next_action` | Do this |
|---|---|
| `realise` | Write the body, append it to `page.md`, call `realise` with its line span, display it |
| `contents` | Enumerate children with `add-nodes` if it has none yet, then display the contents |
| `render` | `render.py --section` — the body already exists, show it unchanged |

`enter` returns `prev_id`, `next_id`, `parent_id`, `last_sibling_id` and `is_end`, so `n`, `p`, `u` and `$` need no further calls. A bare number from the reader is `--position` against the level on screen; out of range, the script names the valid range. When `is_end` is true, pass `--end` to `render.py`.

### Writing a body

Read the node's `promise`, then `state.py trail` and — if the reader has been quizzed — `quiz-report`. Write for this reader's path: a node reached after two related sections needs less setup; a node whose neighbour they answered wrong needs the confusion addressed directly.

Then obey `references/language.md`. Every sentence.

> **MANDATORY — the outline is a contract.** Never invent a node outside the committed outline. New nodes appear only by enumerating a container's children, by explicit reader request, or as `GAPS`. This is what stops a large document from generating forever and what guarantees an `(END)`.

> **MANDATORY — integrity.** In `source` and `mixed` mode, never silently add a fact the source does not contain. Anything you contribute goes to `NOTES` or `GAPS`, marked as such. This rule is what makes Mode 3 trustworthy.

## Mode 2 — test my understanding

Reached with `t`. Read `references/understanding-test.md` before the first question.

One question at a time. Seed the bank with `quiz-add` over realised nodes, then loop: `quiz-next --count 1`, ask, wait, grade, `quiz-record`, cite the lines the script hands back. The script refuses questions on nodes the reader never opened, and picks the weakest node once verdicts exist. Do not choose questions yourself.

Grading is yours: `correct`, `partial`, `incorrect`. The script only stores and counts.

## Mode 3 — what is not in this doc

Reached with `g`, at any time, without walking to the end. Read `references/gap-analysis.md`. It routes you to **exactly one** file in `references/gaps/`. Load that one and no others.

The short version: inventory what the document claims, take the genre checklist, diff, verify each candidate with the `duckduckgo` skill, keep only what changes a decision, then `gaps-add` and append a `GAPS` node to the outline and its body to `page.md`.

Unverified candidates are still reported, stamped `[unverified - model knowledge, confirm before acting]`. Never present a remembered number as a sourced one.

## Bounded handoff rules

**Carry forward:** the session id, the current node id, `next_action`, and one line of what the reader is doing.

**Do not carry forward:** the outline tree, realised bodies, the question bank, the source document, or previous screens. All of it is on disk.

**Reopen narrowly:** `outline --under ID` for one level, `render.py --section` for one section, `quiz-next --count 1` for one question. When you need a slice of a long source file, use `Grep` or the `pdf` skill rather than re-reading the whole thing.

At a phase boundary — entering the quiz, entering gap analysis, resuming after a break — rebuild from `state.py status` and `outline`, not from what you remember of the conversation.

## Checkpoint and resume

The unit of work is one node. After realising each one, `page.md` and `session.json` together hold everything needed to continue.

To resume: `state.py --session-id <slug> status` gives the current node and counts; `outline --under <parent>` gives the level around it; `render.py --section` shows what the reader last saw. Nothing needs to be regenerated.

## Anti-patterns to avoid

- **Do not write the whole page up front.** Commit the outline, realise one node. Generating ahead wastes work and ignores where the reader goes.
- **Do not regenerate a realised section.** It is cached for a reason: text that shifts under the reader breaks navigation and invalidates quiz citations.
- **Do not hand-format output.** `render.py` owns column layout. Typing your own indentation produces ragged screens.
- **Do not print the key list on every screen.** One prompt line. Keys only on `h`.
- **Do not explain what you are about to do.** A manual page has no preamble. Show the section.
- **Do not let an outline grow without end.** If a document seems to have no last node, the outline was never committed properly. Fix the outline.
- **Do not quiz on unread sections, and do not work around the script's refusal.**
- **Do not load more than one genre file in Mode 3.**
- **Do not invent a citation, a line span, or a source.** Line spans come from the script; sources come from a search.
- **Do not soften the register into ordinary prose.** No second person, no encouragement, no closing summary.

## Reference

Read the first two before composing. Read the rest when their mode starts.

- [man-format.md](references/man-format.md) — section vocabulary, genre-to-outline maps, promises, depth, screen layout, navigation keys.
- [language.md](references/language.md) — the CEFR B2 contract: sentences, words, forbidden constructions, numbers and dates, worked rewrites.
- [understanding-test.md](references/understanding-test.md) — question types, how to write and grade one, presentation, closing a session.
- [gap-analysis.md](references/gap-analysis.md) — **read first in Mode 3.** The method, gap kinds, the materiality test, evidence rules, and the routing table below.

Genre checklists for Mode 3. Load exactly one, chosen by the routing table in `gap-analysis.md`:

- [research-paper.md](references/gaps/research-paper.md) — papers, surveys, benchmark studies.
- [technical-book.md](references/gaps/technical-book.md) — textbooks and technical books, whole or by chapter.
- [system-paper.md](references/gaps/system-paper.md) — industry engineering papers and system blog posts.
- [postmortem.md](references/gaps/postmortem.md) — incident reports and outage summaries.
- [design-doc.md](references/gaps/design-doc.md) — design documents, RFCs, architecture decision records.
- [standard-spec.md](references/gaps/standard-spec.md) — standards, specifications, bodies of knowledge.
- [periodical.md](references/gaps/periodical.md) — magazine and journal issues, newsletters.
- [popular-science.md](references/gaps/popular-science.md) — popular science, history, trade non-fiction.
- [policy-position.md](references/gaps/policy-position.md) — regulation, ethics codes, position statements.
- [tool-doc.md](references/gaps/tool-doc.md) — product, API and tool documentation.
- [news-article.md](references/gaps/news-article.md) — news, blog posts, press releases.
