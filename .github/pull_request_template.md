<!--
Guide: https://github.com/opsmill/infrahub/blob/stable/dev/guidelines/pull-requests.md

The reviewer already has the diff and the CI results. Write what neither of them shows.
Delete every section that has nothing to say, and do not write "N/A". A dependency bump,
a lint fix or a typo fix needs one line under "Why".
-->

## Why

<!-- The problem as users, operators or developers meet it today, and what this PR achieves. -->

<!-- Out of scope: what this PR deliberately does not do. -->

Closes <!-- #issue or IFC-1234 -->

## Approach and decisions

<!--
What the diff does not show: the approach, the alternatives you rejected and why, the behavior
that changes, and what deliberately stays the same. Do not list files, functions or commits.

If the change alters a flow between components, the data passed between them or a state
transition, add a short mermaid diagram, with a before and an after when possible.
-->

## Review guide

<!--
Where to start reading, which parts need the most scrutiny, and which parts are mechanical or
generated. Name modules and symbols, not line numbers.
-->

## Evidence

<!--
What CI does not show: a test that fails on the base branch and passes on this branch, checks on
a running stack, measurements, or screenshots of a UI change. Put long logs and tables in a
<details> block. Do not list the commands CI already runs.
-->

Not verified: <!-- what you did not check -->

## Impact

<!-- Keep only the lines that apply. -->

- User-visible change: <!-- no, or yes with the changelog fragment, e.g. `changelog/1234.fixed.md` -->
- Upgrade or migration:
- Configuration:
- API:
- Performance:

## Open questions

<!--
Written by the human author, never by an agent: the decisions you want the reviewer to challenge,
and the questions you could not settle yourself.
-->

## Checklist

- [ ] Changelog fragment added, or the change is not visible to users
- [ ] External docs updated, or not needed
- [ ] Internal docs (`dev/`, `AGENTS.md`, `.agents/`) updated, or not needed
