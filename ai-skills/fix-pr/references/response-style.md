# Response style

How a reply to a reviewer reads. This governs text another person will see.

## Voice

Write to a colleague who spent their time reading your change. Direct,
specific, and short.

- Lead with what happened: fixed, already handled, or not changing and why.
- Then the evidence: the commit, or the line and test that support the
  disposition.
- Stop. A reply that keeps going past its evidence reads as persuasion.

## A fix reply

Two things, always:

> Fixed in `a1b2c3d` — the page size is now clamped to the configured maximum in
> `CheckoutController#list` before it reaches the repository.

The commit lets the reviewer jump to it. The solution path lets them decide
whether they even need to. A reply of "done" or "good catch, fixed" makes them
go looking, which is the work they were trying to save by pointing it out.

Where the fix differs from what the reviewer suggested, say so and why:

> Fixed in `a1b2c3d`, though not with a `@Max` on the parameter — that rejects
> the request where the existing endpoints clamp. Clamped to match
> `OrderController#list`.

## A non-fix reply

Evidence, not reasoning. The reviewer needs something they can check.

> Not changing this — `accountId` comes from the authenticated principal in
> `CheckoutRequestMapper:34`, never from the body, so it cannot be null here.
> `CheckoutMapperTest#rejectsUnauthenticated` covers the case.

Versus a reply that will not survive contact with a careful reviewer:

> I don't think this can be null.

If the only support is judgment, the disposition was not `FALSE_POSITIVE` — it
was unverified, and it needs to go back through evaluation.

## An outdated or already-fixed reply

Point at the commit, and be plain that it predates the comment. That is not a
criticism of the reviewer; a stale anchor is normal on an active branch.

> Already handled in `9f8e7d6`, pushed before this comment landed — the null
> check moved into the mapper.

## A deferred reply

Say what it is, where it went, and that this change is complete without it.

> Valid, but outside this change's scope — it is the limit-increase flow, not
> checkout. Raised on ORD-503 with the evidence. This change's deliverable
> stands on its own.

Never defer something silently, and never defer something the reviewer will
reasonably read as part of this change without saying why it is not.

## A question

Answer it. Then state what changed, if anything did.

> It is per-account, not per-currency — `AccountLimit` has no currency
> component, and the flow document's Rules section §3 specifies a single limit.
> No change.

## What not to write

- No apology. "Sorry, my bad, good catch" three times in a review is noise.
- No thanks on every comment. Once in the summary is plenty, if at all.
- No defensiveness. A reviewer who was wrong gets evidence, not an argument.
- No "as discussed" pointing at a conversation the thread cannot see.
- No emoji.
- No promise of future work with no owner. "Will address in a follow-up" needs
  the work item, or it is not a commitment.

## Never claim work that did not happen

The one failure mode that damages trust irreparably: a reply citing a fix that
is not in the branch, a test that does not exist, or a commit that does not
contain what the reply says it does.

Every fix reply is composed from the engine's actual result — the commit hash it
returned and the files it reported changing. Never from what the session
intended to do.
