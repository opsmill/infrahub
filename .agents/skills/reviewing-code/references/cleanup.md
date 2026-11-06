# Cleanup and consistency

The rule reviewers read one area at a time, the Design reviewer looks at how the files depend on
each other, and the New files reviewer reads only the files the change adds. None of them reads
every changed line for comments that say nothing, code an earlier commit of the branch left
behind, names that do not match, or code that could be shorter. A branch built over several
agent sessions collects all four: each session adds comments and helpers for its own step, and a
later session replaces the step without removing them.

## Inputs

Give one reviewer per area:

- `.agents/rules/code-design.md` and `.agents/rules/code-doc-style.md`, to read with the Read
  tool before the code
- the area's changed files from the manifest, and `git diff origin/<base>...HEAD -- <files>`
- the branch's commits, oldest first: `git log --reverse --format='%h %s' origin/<base>..HEAD`
- the folder of each changed file, to compare with its sibling files

The reviewer starts its answer with `READ:` and one line per file read, as in the rule check.
Grade a finding P2 when one of the two rules covers it, P3 otherwise. Report only lines the
change adds or changes, and code the change leaves unused or untrue.

## Questions

### Comments

For each comment and docstring the change adds or keeps beside a changed line:

- Does it restate the code below it, narrate the change, or describe the code's history? Delete
  it.
- Is it still true for the code beside it? A later commit can change the code and leave the
  comment of an earlier one. Fix it or delete it.
- Does it hold a ticket or spec ID (`[A-Z]{2,}-[0-9]+`, `\bT[0-9]{3}\b`, `issues/[0-9]+`), history
  words (`used to`, `no longer`, `previously`, `instead of`, `now`, `new`), a step of a plan
  (`Phase 2`, `step 3`, `for now`), commented-out code, a banner, or a `TODO`? Delete it, or
  move the follow-up work to an issue.
- Would a clearer name or a named function make the comment unnecessary? Propose the name.

### Leftovers from earlier commits

Read the commits in order. For each function, class, component, hook, constant, type, parameter,
option, flag, fallback, export, test, fixture and file that an earlier commit added:

- Does the final code still use it? Search for its callers (`git grep -n '<name>'`). Flag it when
  nothing calls it, or only its own test does.
- Did a later commit replace the approach it served? Flag the parts of the old approach that are
  still there: a branch for a case that can no longer happen, a parameter every caller passes
  with the same value, a fallback for data the new code never produces, a test for the old
  behaviour.
- Is it debug output, a temporary log line, a scratch file or a sample value left from testing?

A leftover is a Fix: delete it in the same change. When a caller outside the manifest uses it,
it is not a leftover: drop the finding.

### Names and placement

For each file, function, class, component, hook, constant and type the change adds or renames,
in changed files as well as new ones:

- Does the name say what it holds or does, as the Naming section of `code-design.md` asks?
- Does it follow the pattern of its siblings in the same folder: the same file name pattern
  (`use-*.ts`, `*-query.ts`, `test_*.py`), the same suffixes and the same word order? Name the
  sibling it departs from.
- Does the change use one term for each concept, in names, comments, test names and user-visible
  text? List each concept that has two names.
- Is the file in the folder where its siblings of the same kind live? Leave the question of which
  layer owns the code to the architecture check.
- After a rename, does any caller, test name, doc or spec still use the old name?

### Simpler code

For each function the change adds or changes:

- Can it be shorter with the same behaviour: a condition that is always true or always false, a
  check repeated by its caller, a variable used once, nested conditions that one early return
  removes, a loop a standard library or existing helper call replaces?
- Does the change repeat a block of its own code in two places?
- Does it re-implement something the language, the framework or an existing helper of the
  codebase already does? Name the helper as `file:line`.

Leave new layers, abstractions and options to the Design check.

### Consistency

- Within the change, is the same job done the same way: error handling, loading and empty
  states, logging, query structure, test setup and assertions?
- Compared with the closest sibling feature in the codebase, does the change do the same job in
  another way? Name the sibling `file:line`. Flag it unless the spec, the plan, the pull request
  description or a commit message gives a reason for the difference.

## How Phase 2 and Phase 3 handle these findings

Merge them with the other findings and drop duplicates: a Design Simplicity finding and a
Simpler code finding on the same lines are one finding. A rename or a removal that reaches a
caller outside the manifest is Ask, as Phase 2 step 5 says. In Phase 3, show the cleanup findings
as one group, so the user can approve them together.
