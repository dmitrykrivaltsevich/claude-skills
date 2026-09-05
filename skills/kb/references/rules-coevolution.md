# Rules Co-Evolution

The file `.kb/rules.md` is the per-KB operating manual. It starts from a template but MUST evolve as the KB grows. Unlike SKILL.md (which is generic), rules.md captures decisions specific to THIS knowledge base.

**This is NOT optional.** After 20+ sources, the rules.md should have grown significantly from its template. If it hasn't evolved, you're not doing this step. The mandatory check in Phase 6 of kb:add and step 6 of kb:lint exist precisely because LLMs tend to skip this — DO NOT SKIP IT.

**When to update rules.md** (propose the change to the user first):

| Trigger | What to add |
|---|---|
| User corrects your entry style or structure | Record the preference as a rule |
| A new entry type pattern emerges (e.g. "recipe", "theorem", "code-analysis") | Add it to the entry types in rules.md with directory and frontmatter. Create the directory. Follow the Custom Entry Types section of the entry-types reference linked from SKILL.md |
| User establishes a tagging convention | Document the tag taxonomy |
| User sets a scope boundary ("this KB is only about X") | Add a scope section |
| A naming conflict arises (two concepts with similar names) | Add a disambiguation rule |
| The KB reaches a size where new conventions help | Add organizational rules (e.g. sub-directories, index sections) |
| User requests a custom workflow | Document it as a named operation |
| You notice a recurring extraction pattern | Codify it so future sessions follow it |
| A source type is new to the KB (e.g. first codebase, first legal document) | Add source-type-specific extraction guidance |

**How to update**: Read the current rules.md, propose the specific change to the user, and apply it only after approval. Never silently modify rules.md. In unattended operations (`kb:lint`), there is no one to approve: append the proposal to `.kb/rules-proposals.md` instead and carry on.
