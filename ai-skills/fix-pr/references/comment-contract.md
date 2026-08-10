# Comment contract

Fetching the complete feedback graph on a pull request, and splitting it into
items that can each be dispositioned and answered.

## Contents

- Why completeness is the hard part
- The five sources
- Fetching
- Thread state
- Splitting into atomic recommendations
- What is not actionable
- Chronology
- Checking against the current branch

## Why completeness is the hard part

GitHub exposes review feedback through several different endpoints, and each one
paginates. A single unpaginated call to the obvious endpoint returns a plausible
subset — enough to look complete, and missing the thread where the reviewer
raised the real objection.

From the author's side that is indistinguishable from ignoring it. So
completeness is checked and stated, not assumed: the result records whether the
graph is complete, and names what is missing when it is not.

## The five sources

| Source | Contains |
| --- | --- |
| issue comments | top-level discussion on the pull request |
| reviews | each review's summary body and its event (`COMMENT`, `APPROVE`, `REQUEST_CHANGES`) |
| review comments | inline comments with path, line, side, and diff hunk |
| review threads | the reply chain, resolution state, and outdated state |
| commits | what has been pushed since each comment |

The review summary body is the one most often missed. A reviewer who writes
"three things, all in the summary" leaves nothing inline, and a fetch that reads
only inline comments finds no feedback at all.

## Fetching

Use the `gh` CLI. Paginate every list — never take the first page as the whole.

Thread resolution state is not exposed by the REST endpoints; it comes from the
GraphQL `reviewThreads` connection. An author-side workflow needs it, because
resolving an already-resolved thread and re-answering a settled point both make
the conversation worse.

Fetch in this order, so later steps can be checked against earlier ones:

1. the pull request itself — head, base, state, and the commit list;
2. reviews, with their bodies and events;
3. review comments, with their anchors;
4. review threads with resolution state, joined to the comments by id;
5. issue comments.

Record the count from each source. A join that drops a comment is a bug worth
catching here rather than discovering when the reviewer asks why they were
ignored.

## Thread state

Three properties, and each changes what should happen:

- **resolved** — someone marked the conversation settled. Do not re-answer it.
  Do check whether it was resolved without a reply, which is a finding in
  `recheck` mode.
- **outdated** — the line it anchored to has changed. The point may still be
  valid; the anchor is not. Check the current code, and if the point no longer
  applies, that is `OUTDATED` with the commit that changed it.
- **collapsed by a force push** — the comment survives but its diff context may
  be gone. Reconstruct the context from the commit the comment referenced, and
  say so if it cannot be reconstructed.

## Splitting into atomic recommendations

One comment is frequently several requests. Split so each item can carry its own
disposition and its own reply.

Split on:

- separate numbered or bulleted points;
- a request plus a question;
- a request about one file plus an aside about another;
- a specific finding plus a general observation.

Do not split:

- a finding and its own justification;
- a finding and its suggested fix;
- a single point restated for emphasis.

Keep the verbatim text on every item, and keep the source anchor — the comment
id, author, URL, path, line, and side. The reply is posted to that anchor, and
one reply per comment means several items may share a target: compose one reply
covering all of that comment's items rather than posting three replies to the
same line.

## What is not actionable

These get no reply and no disposition, and recording that keeps them out of the
`NO_RESPONSE` count:

- a bot comment: a coverage report, a CI status, a formatting notice;
- an approval with no content;
- a reaction or an acknowledgement;
- the author's own earlier comments;
- a comment on a commit that has since been dropped from the branch, where the
  code it referenced no longer exists in any form.

Everything else is actionable, including comments that turn out to be wrong.
Being wrong earns a reply with evidence, not silence.

## Chronology

Order everything by creation time across all five sources, interleaved. It
matters because reviewers correct themselves: a later comment saying "ignore my
previous point, I misread" supersedes the earlier one, and a workflow that
processes threads independently will dutifully implement a retracted request.

Carry the relevant ordered context on each item so the engine's evaluation can
see it.

## Checking against the current branch

An item's evaluation needs to know what the branch contains **now**, not what it
contained when the comment was written. Before evaluation:

- record the commits pushed since each comment;
- for an inline comment, read the current content at that anchor;
- note where the anchor no longer resolves.

This is what distinguishes `ALREADY_FIXED` from `REAL_FIX`, and `OUTDATED` from
`FALSE_POSITIVE` — four dispositions that get four different replies, and
getting them wrong reads as either ignoring the reviewer or claiming work that
was not done.
