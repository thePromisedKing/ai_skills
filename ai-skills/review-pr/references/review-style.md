# Review style

How an outward-facing review reads. This governs text another person will see —
the review body and its inline comments.

## Voice

Write to a competent colleague. Direct, specific, and about the code.

- State the problem, then the consequence, then the smallest fix. In that order,
  because the consequence is what makes the fix worth doing.
- Anchor to the line. A finding without a location makes the author search.
- Be concrete about the failure: "with `pageSize=100000` this loads the whole
  table into memory" beats "this could be a performance issue".
- Say what you checked when it is not obvious. It saves the author re-deriving
  it, and it shows the finding was verified rather than pattern-matched.

## What not to write

- No praise padding. "Great work overall, just a few small things" says nothing
  and delays the content.
- No hedging that hides a real finding. "Maybe consider possibly looking at" is
  a `BLOCKING` finding the author will skip.
- No false hedging in the other direction either — a `PLAUSIBLE` finding says it
  is plausible and says what would confirm it.
- No lecturing. Cite the standard or the requirement; do not explain why testing
  matters.
- No comment on the author. The review is about the change.
- No emoji. No exclamation marks.
- No "nit:" on something that is not actually a nit.

## Marking severity

Make severity visible without a taxonomy the reader has to learn:

- A `BLOCKING` finding says what breaks and under what conditions.
- An `IMPORTANT` finding says what it will cost and when that cost arrives.
- A `MINOR` finding is labeled as optional in plain words, or left out. Three
  minor findings are context; fifteen are noise that buries the blocking one.

## Questions

A genuine question is a legitimate review comment — sometimes the most valuable
one. Ask it as a question, and say what answer would resolve it:

> Is `accountId` guaranteed non-null here? If it comes from the authenticated
> principal, this is fine; if it comes from the request body, line 88
> dereferences it before validation.

Do not disguise a finding as a question. "Have you thought about concurrency?"
is a finding the author has to reconstruct.

## The review body

The summary that accompanies the inline comments states:

- what the change does, in one or two sentences, so it is clear the reviewer
  read it;
- the blocking findings, listed;
- what was checked and found sound — briefly, and only where it is useful
  evidence of coverage;
- what was not checked, and why: an unread portion of a large diff, a lens
  skipped, a behavior only a manual test could prove.

That last point matters most. A review that does not say what it did not cover
implies it covered everything.

## Re-review

On a second round, respond to what changed:

- confirm the findings that are now resolved, by name;
- state which remain and why the change did not resolve them;
- raise new findings only in code that changed, or in something the first round
  genuinely missed — and say which it was.

Do not re-litigate a point the author answered with evidence. Do not silently
drop a finding either; if it no longer applies, say so.
