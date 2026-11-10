# Cleanup

A branch built over several sessions keeps the comments, helpers and tests of steps that later
commits replaced. This check reads every changed line for them.

Give one reviewer per area:

- `.agents/rules/code-design.md` and `.agents/rules/code-doc-style.md`
- the area's changed files and `git diff origin/<base>...HEAD -- <files>`
- the commits, oldest first: `git log --reverse --format='%h %s' origin/<base>..HEAD`

It reports only lines the change adds or changes, and code the change leaves unused or untrue.

## Comments

For each comment and docstring on or beside a changed line, delete or fix it when it:

- restates the code, narrates the change or describes its history
- is no longer true for the code beside it, often because a later commit changed the code
- holds a ticket or spec ID (`[A-Z]{2,}-[0-9]+`, `\bT[0-9]{3}\b`, `issues/[0-9]+`), a plan step
  (`Phase 2`, `step 3`, `for now`), commented-out code, a banner or a `TODO`
- could be replaced by a clearer name; propose the name

## Leftovers from earlier commits

For each function, class, component, hook, constant, type, parameter, flag, fallback, export,
test, fixture and file an earlier commit added, flag it when:

- nothing calls it, or only its own test does (`git grep -n '<name>'`)
- it served an approach a later commit replaced: a branch for a case that can no longer happen,
  a parameter every caller passes with the same value, a fallback for data nothing produces, a
  test for the old behaviour
- it is debug output, a temporary log line, a scratch file or a sample value

A leftover is a Fix. When a caller outside the manifest uses it, drop the finding.

## Names and placement

For each file, function, class, component, hook, constant and type the change adds or renames:

- Does the name say what it holds or does?
- Does it follow its siblings in the same folder: file name pattern (`use-*.ts`, `*-query.ts`,
  `test_*.py`), suffixes, word order? Name the sibling.
- Does each concept have one name across names, comments, tests and user-visible text?
- Is the file in the folder where files of the same kind live?
- After a rename, does any caller, test name, doc or spec keep the old name?

## Simpler code

For each function the change adds or changes, flag:

- a condition that is always true or false, a check the caller already makes, a variable used
  once, nesting an early return removes
- a block repeated within the change
- code the language, the framework or an existing helper already provides; name it as
  `file:line`

## Consistency

- Within the change, is each job done one way: error handling, loading and empty states,
  logging, queries, test setup?
- Does the change do a job differently from the closest sibling feature (`file:line`) with no
  reason written in the spec, plan, pull request description or a commit message?

## New files and tests

For each file the change adds (`git diff --name-only --diff-filter=A origin/<base>...HEAD`, plus
untracked files in scope):

- Is it needed, or does an existing helper, constant, type or component do the job?
- For each test, name the code change that would make it fail. Flag a test with none, and a test
  that repeats a case another test covers.
- For each negative assertion (`toBeNull()`, `not.toBeInTheDocument()`, `assert X not in ...`),
  check that the fixture can produce X. When nothing produces X, the assertion always passes:
  name the fixture change that would let it fail.

## In Phase 2 and Phase 3

A Design Simplicity finding and a Simpler code finding on the same lines are one finding. In
Phase 3, show the cleanup findings as one group the user can approve together.
