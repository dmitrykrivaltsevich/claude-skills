# Language contract

Every word displayed by this skill obeys this contract. Apply it while writing, not as a later pass.

The reader is fluent but not a native speaker. They read English technical material daily. They are not helped by simplified content — they are slowed down by idiom, by long subordinate chains, and by vocabulary that carries meaning only for a native ear. Write for **CEFR B2**, at the discipline of **ASD-STE100 Simplified Technical English**.

## Contents

1. [Sentences](#sentences)
2. [Words](#words)
3. [What is forbidden](#what-is-forbidden)
4. [Numbers, dates and units](#numbers-dates-and-units)
5. [Terminology](#terminology)
6. [Source language](#source-language)
7. [Worked rewrites](#worked-rewrites)

## Sentences

- One idea per sentence. Around 20 words is the ceiling for a procedural sentence.
- Subject, verb, object. Put the actor first and the action second.
- Active voice. Name who acts: `the parser rejects the input`, not `the input is rejected`.
- One subordinate clause at most. Split rather than nest.
- Positive form. `The list must be sorted` beats `The list must not be unsorted`.
- No sentence begins with a pronoun whose referent is in the previous sentence. Repeat the noun.

## Words

- Prefer a single verb to a verb plus particle: `tolerate` not `put up with`, `start` not `kick off`, `remove` not `get rid of`, `continue` not `carry on`, `discover` not `find out`.
- Prefer the international technical word, which is usually the Latinate one: `terminate`, `evaluate`, `allocate`, `sufficient`. These are recognisable across languages; Anglo-Saxon phrasal constructions are not.
- Use one word per concept for the whole page. Never alternate between synonyms.
- Expand every acronym at first use: `TCC (Transparency, Consent, Control)`. Once expanded, use the short form only.
- Keep technical terms in English even when the source is in another language.

## What is forbidden

| Forbidden | Because | Instead |
|---|---|---|
| Idioms — `a ballpark figure`, `the elephant in the room`, `low-hanging fruit` | Meaning is not derivable from the words | State the fact |
| Metaphor as explanation — `the database is a warehouse` | The reader must know the vehicle to reach the tenor | Describe the mechanism |
| Phrasal verbs | Particle changes meaning unpredictably | A single verb |
| Cultural or sporting references — `out of left field`, `a googly` | Not shared knowledge | Remove |
| Hedges — `arguably`, `somewhat`, `it could be said`, `rather` | Add words, remove information | Assert, or state the uncertainty precisely |
| Contractions — `doesn't`, `it's` | Harder to parse quickly, and `it's` collides with `its` | Write both words |
| Tag and negative questions — `isn't it?`, `don't you need X?` | Answer polarity is ambiguous across languages | Ask directly |
| Double negatives — `not uncommon` | Requires two inversions | `common` |
| Long noun stacks — `data ingestion pipeline failure rate threshold` | No grammatical signal for how the words group | Break with prepositions |
| `Should` for requirement | Reads as advice in some languages | `must`, or state the consequence |

## Numbers, dates and units

- Dates in ISO 8601: `2026-09-05`. Never `09/05/26`, which reads as two different days in different countries.
- Times with an explicit zone: `14:30 UTC`.
- Decimal point, not decimal comma. Space as the thousands separator: `1 048 576`.
- Spell out the power for large numbers on first use: `one billion (10^9)`. Scale words differ between languages.
- Always give the unit. Always give the denominator of a percentage: `12% of the 400 requests`, not `12%`.
- Ranges with `to`, not a dash: `5 to 9 nodes`.

## Terminology

Fix the vocabulary for the page at the start, and keep it. If the source calls the same thing a `job`, a `task` and a `unit of work`, choose one, use it everywhere, and record the others once in `NOTES`.

## Source language

Sources are often not in English. Render the page in English regardless of the source language, unless the reader asks otherwise. When you translate a term, give the original once in parentheses at first use, then use the English term:

```
The magazine calls this a supply chain attack (атака на цепочку поставок).
```

Quote a passage in its original language only when the wording itself is the subject.

## Worked rewrites

| Before | After |
|---|---|
| It's worth noting that the scheduler will typically end up dropping tasks that have been sitting around for too long. | The scheduler drops a task after 30 seconds in the queue. |
| This isn't a bad approach, but you might want to think about whether it scales. | This approach works below 1 000 requests per second. Above that, latency grows. |
| The system leverages a best-of-breed caching layer to turbocharge reads. | A cache in front of the database serves repeated reads. |
| Don't you need to set the flag first? | Set the flag first. |
| Performance was somewhat impacted by the change. | The change increased median latency from 12 ms to 38 ms. |
| We'll dive into the nuts and bolts of the protocol below. | `DESCRIPTION` states how the protocol works. |
