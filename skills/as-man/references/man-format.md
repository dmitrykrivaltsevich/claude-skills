# Manual page format

How to shape any material into a manual page, and how the page appears on screen.

## Contents

1. [Section vocabulary](#section-vocabulary)
2. [Genre to outline maps](#genre-to-outline-maps)
3. [Writing a promise](#writing-a-promise)
4. [Choosing depth](#choosing-depth)
5. [Page identity](#page-identity)
6. [Screen layout](#screen-layout)
7. [Navigation keys](#navigation-keys)
8. [Anti-patterns](#anti-patterns)

## Section vocabulary

Standard sections, in the order `man` uses them. Use the ones the material needs; omit the rest. Never invent a synonym for one of these.

| Section | Holds |
|---|---|
| `NAME` | The subject and a one-line summary, in the form `subject - summary`. Always present. |
| `SYNOPSIS` | The shortest complete form of the thing: a signature, a rule, an equation, a claim in one line. |
| `DESCRIPTION` | How it works. The main body. |
| `OPTIONS` | The variants, dialects, parameters, or knobs. |
| `EXAMPLES` | Worked cases. Each example shows input and result. |
| `EXIT STATUS` | Outcomes and what each one means. |
| `ENVIRONMENT` | What must be true outside the thing for it to work. |
| `FILES` | Artefacts it reads or writes. |
| `DIAGNOSTICS` | Errors and what they indicate. |
| `NOTES` | Facts that do not fit elsewhere, including anything you added that the source did not contain. |
| `CAVEATS` | Conditions under which the material misleads. |
| `BUGS` | Known defects and limits. |
| `HISTORY` | How it came to be, and what changed. |
| `SEE ALSO` | Neighbouring subjects, as `name(section)` references. |
| `AUTHORS` | Who produced the source. |
| `GAPS` | Appended by the gap mode only. Never write it by hand. |

Manual section numbers: `1` commands, `2` system calls, `3` library functions, `5` file formats, `7` concepts and conventions, `8` administration. A topic explainer is almost always `(7)`.

## Genre to outline maps

The top outline level for each kind of material. These are starting shapes, not templates to force.

| Material | Top level |
|---|---|
| Concept or topic | `NAME`, `SYNOPSIS`, `DESCRIPTION`, `OPTIONS`, `EXAMPLES`, `CAVEATS`, `SEE ALSO` |
| Tool, API, product doc | `NAME`, `SYNOPSIS`, `DESCRIPTION`, `OPTIONS`, `EXAMPLES`, `DIAGNOSTICS`, `FILES`, `BUGS`, `SEE ALSO` |
| Research paper | `NAME`, `SYNOPSIS` (the claim), `DESCRIPTION` (method), `RESULTS`, `CAVEATS` (threats to validity), `SEE ALSO` (related work) |
| Book | Its own parts, then chapters, then sections. Add `NAME` and `SYNOPSIS` above them. |
| Magazine or journal issue | `NAME`, `SYNOPSIS` (the issue theme), then one node per article |
| Standard or specification | `NAME`, `SYNOPSIS`, `DESCRIPTION`, `CONFORMANCE`, `OPTIONS`, `HISTORY`, `SEE ALSO` |
| Design document, RFC, ADR | `NAME`, `SYNOPSIS` (the decision), `DESCRIPTION`, `ALTERNATIVES`, `CONSEQUENCES`, `CAVEATS` |
| Post-mortem | `NAME`, `SYNOPSIS` (impact in one line), `TIMELINE`, `DESCRIPTION` (mechanism), `DIAGNOSTICS`, `CAVEATS` |
| News article or blog post | `NAME`, `SYNOPSIS`, `DESCRIPTION`, `SEE ALSO` |
| Contract or policy | `NAME`, `SYNOPSIS`, `DESCRIPTION`, `OPTIONS` (elections and exceptions), `CAVEATS`, `SEE ALSO` |

When the source has its own table of contents, use it. A reader who knows the book must recognise the outline.

## Writing a promise

Every node carries a one-line `promise` stating what that node will contain. It is the only thing you will have when you write the body many turns later, so it must be specific.

- Good: `How Datalog evaluates recursion, and why it terminates.`
- Bad: `More about recursion.`

A promise names the question the node answers. If two promises answer the same question, merge the nodes.

## Choosing depth

Depth comes from the material, never from a fixed number.

- One level when every node is a leaf you can write in a screen: a concept, an article, a tool.
- Two levels when the material has named divisions: a book's chapters, an issue's articles with parts.
- Three levels when a division is itself too large to read at once: part, chapter, section.

Commit only the top level when the page opens. Enumerate a node's children when the reader enters it, not before. A 600-page book and a five-line concept use the same model at different depths.

## Page identity

`NAME` is always the first node, and its body is exactly one line:

```
datalog - a declarative query language for deductive databases
```

The summary is a noun phrase, lower case, no final full stop. This line is what a reader sees in a contents list, so it must stand alone.

## Screen layout

`render.py` handles layout. Do not hand-format output.

- Section headings are upper case and flush left.
- Bodies are indented seven columns; subsection headings three.
- Text wraps at 80 columns.
- Code blocks are reproduced exactly and may overflow, because rewrapping code would change its meaning.
- Consecutive `Label:  value` lines become a tagged paragraph: the values line up in one column and a long value wraps under it. This is how `man` sets `ENVIRONMENT`, `FILES`, `EXIT STATUS` and `DIAGNOSTICS`, and it is how a `GAPS` entry is laid out.

Write a tagged block as plain lines, one field per line, with at least two spaces after each colon:

```
Kind:         omission
Materiality:  high
Missing:      Cross-zone traffic is billed per gigabyte in each direction.
```

The label is one or two words. A sentence that merely contains a colon stays prose, so `There are two kinds: stratified and unstratified.` wraps normally.

Print the rendered text inside a fenced code block so the terminal keeps the column alignment.

## Navigation keys

Show these only when the reader presses `h`. The prompt line stays one line.

```
n  next             t  contents        u  up a level    ?  test my understanding
p  previous         $  last section    /  search        !  what is missing
12 go to entry 12   h  keys            q  quit
```

Accept the full word as well as the key: `next`, `contents`, `gaps`, `test`. The reader is typing into a chat, not a terminal.

A bare number is a jump to that entry of the level currently displayed, which is the numbering a contents screen shows. `go to 12` and `12` mean the same thing. A number is never a search term: to find the digits themselves, the reader uses `/`.

The prompt line under every screen:

```
datalog(7)  12/27  RECURSIVE QUERIES                              (h for keys)
```

At the end of the page:

```
datalog(7)  27/27  SEE ALSO                                  (END — ! for gaps)
```

## Anti-patterns

- **Do not write an introduction.** A manual page starts at `NAME` and states facts. There is no welcome, no summary of what you are about to say, no closing paragraph.
- **Do not address the reader.** No "you will learn", no "let us look at". State what the thing does.
- **Do not invent sections.** Use the vocabulary above. A section called `OVERVIEW` or `GETTING STARTED` means you have stopped writing a manual page.
- **Do not pad a thin node.** If a node has one fact, its body is one sentence. Length is not a goal.
- **Do not front-load caveats.** `DESCRIPTION` says what happens; `CAVEATS` says when it fails.
- **Do not repeat the promise as the first sentence of the body.** The reader has already read it in the contents.
