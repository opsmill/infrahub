# Upgrade Note for the Consolidated Changelog

This is the text for the upgrade section of the release notes. It goes in when the Towncrier fragments of the
feature are consolidated (T149). It is not a Towncrier fragment.

## Text

Before you upgrade, run `infrahub db ownership-report` on the database of the release before. The command changes
no data. The report lists:

- The attributes that a repository owns. The upgrade removes these owners (graph migration `m086`).
- The attributes that a node other than an account, an account group or a repository owns. The upgrade keeps these
  owners.
- The relationships whose links have owners. The upgrade keeps these owners.
- The attributes with values that have `is_protected` set. `is_protected` is deprecated.

The report counts only open edges. A branch can still read an owner edge that the default branch closed after the
start of the branch, and the report does not list that edge.

Keep the output of the report from before the upgrade. The upgrade closes the owner edges from attributes to
repositories, so after the upgrade the first section of the report is empty, and the command prints a warning about
it. During the upgrade, `m086` prints the number of owner edges that it closed for each repository.
