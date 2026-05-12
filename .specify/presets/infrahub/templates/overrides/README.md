# Per-user overrides

This directory holds per-user defaults consumed by the Infrahub `speckit.taskstoissues` override (assignee, team, extra labels). The slug for your override file is derived from `git config user.email`: lowercase the address and replace every non-alphanumeric character with `-`. For example, `pol@opsmill.com` becomes `pol-opsmill-com.yml`.

Real override files are gitignored; only `example.yml` and this README are tracked. If the skill cannot find a file matching your slug, it will surface a prompt of the form `> No override found for <slug>. Copy example.yml to <slug>.yml and fill in assignee/team before retrying.` — copy `example.yml`, edit `assignee.email` and `team.name`, and re-run.
