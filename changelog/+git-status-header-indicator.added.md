Added a Git status indicator to the application header. It turns red with a pulsing dot when any Git repository on the branch you are viewing has failed to import, on every page, and links straight to the repository list filtered to the failures.

It reads repository sync status rather than task state, so an import that left the branch broken is reported even when the task that ran it finished successfully. On a branch with no Git repositories the indicator stays in place but inactive, and it always reports current status regardless of the time-frame selector.
