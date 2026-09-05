# Testing understanding

One question at a time. Grade it. Say where to re-read. Then adapt.

## Contents

1. [The loop](#the-loop)
2. [Question types](#question-types)
3. [Writing a good question](#writing-a-good-question)
4. [Grading](#grading)
5. [Presentation](#presentation)
6. [Closing a session](#closing-a-session)
7. [Anti-patterns](#anti-patterns)

## The loop

1. `state.py quiz-next --count 1` — the script picks: unanswered questions first, weakest node first. Never guess the next question yourself.
2. Ask it. Show which section it comes from. Stop and wait.
3. Grade the answer. Assign `correct`, `partial` or `incorrect`.
4. `state.py quiz-record` — persist the verdict.
5. Say what was right, what was missing, and cite the exact lines to re-read.
6. Return to step 1 until the reader stops or `pending_count` reaches zero.

Seed the bank with `quiz-add` before the first question. Two to four questions per realised node is enough. The script refuses questions on nodes the reader has not opened, which is the point: a reader can only be tested on text they have seen.

## Question types

| Type | Asks | Example shape |
|---|---|---|
| `recall` | A stated fact | What is the default timeout? |
| `application` | Use of a rule in a concrete case | The queue holds 40 items and the limit is 32. What happens? |
| `discrimination` | The difference between two things readers merge | When is a service the wrong choice and an ingress the right one? |
| `consequence` | What breaks if a step is skipped | The flag is not set before the first write. What fails, and when? |
| `transfer` | The idea in a setting the page never mentions | The page describes this for queues. What would it mean for a cache? |
| `trap` | The most likely misreading of the section | Does a restart preserve the address? |

Each realised node should be covered by at least one `recall` or `application` question. Reach for `discrimination` and `trap` where the section has a genuine confusion in it — not for every node.

## Writing a good question

- Answerable from the page alone. If it needs outside knowledge, it is testing something else.
- One answer. If two readings are both defensible, the question is broken, not the reader.
- No yes-or-no question unless it is followed by "why".
- The `answer_key` states what a correct answer must contain, not a model paragraph. List the required elements.
- The question obeys the language contract in `language.md`, including the ban on negative and tag questions.

A `trap` question must have a real trap: something the section states precisely and a hurried reader inverts. Do not manufacture one by being vague.

## Grading

You grade. The script only stores the verdict and counts it.

| Verdict | Meaning |
|---|---|
| `correct` | Every required element of the answer key is present. Wording may differ. |
| `partial` | Some required elements present, none of them wrong. |
| `incorrect` | A required element is missing and something stated is wrong, or the answer addresses a different question. |

Rules:

- Grade the content, not the English. The reader is not being tested on grammar.
- A right answer in different words is `correct`. Do not require the page's phrasing.
- A right answer with an added wrong claim is `partial` at best. Say which part is wrong.
- If the page is genuinely ambiguous at that point, say so, grade `correct`, and note that the section needs rewriting.

## Presentation

Ask like this:

```
QUESTION 3          DESCRIPTION

A pod restarts. What happens to the address other pods were using?
```

Respond like this:

```
PARTIAL

Correct: the pod gets a new address.
Missing: the old address is not reassigned, so callers holding it fail.

SEE: datalog(7) DESCRIPTION, lines 30-38
```

The citation comes from the line span recorded when the node was realised, returned by `quiz-record`. Never cite a line span you did not get from the script.

## Closing a session

When the reader stops, run `quiz-report` and give a short summary: how many were asked, the verdict counts, and the weak nodes named with their line spans. Nothing else — no encouragement, no score interpretation.

The weak nodes matter beyond the quiz: when the reader later opens a node that has not been written yet, the recorded misses tell you what to make explicit in it.

## Anti-patterns

- **Do not ask more than one question at a time.** The mode is a conversation.
- **Do not reveal the answer key with the question.**
- **Do not soften an incorrect verdict.** Say it plainly and point at the lines.
- **Do not quiz a node the reader skipped.** The script blocks it; do not work around it by asking without recording.
- **Do not ask about the page's structure.** "Which section covers recursion?" tests navigation, not understanding.
- **Do not praise.** Report the verdict and move on.
