Added a repository sync status indicator to the application header. It turns red with a pulsing dot when any Git repository on the branch you are viewing has failed to import, on every page, and links straight to the repository list filtered to those failures.

It reads repository sync status rather than task state, so an import that left the branch broken is reported even when the task that ran it finished successfully. When nothing is failing it links to the full repository list, and it always reports current status regardless of the time-frame selector.
