# jira-branch

Overrides `speckit.git.feature` from the git extension bundled with spec-kit, so that `/speckit.specify` creates a feature branch only with a JPD (`infp-<n>`) or Jira epic (`ifc-<n>`) reference. The branch is named `<short-name>-<ticket-id>`, for example `user-auth-infp-460`.

It replaces the [`infrahub` preset](https://github.com/opsmill/infrahub/tree/4d9fd0f0a469217aada697cb5ef306f7ef485f78/dev/spec-kit/presets/infrahub) of opsmill/infrahub.

## Install

In a repo that has the `infrahub` preset, remove it first with `specify preset remove infrahub`. If `.specify/extensions/git/` does not exist, install the git extension before the preset, otherwise the override is skipped:

```bash
specify extension add git
git clone -b <tag> https://github.com/opsmill/opsmill-speckit
specify preset add --dev opsmill-speckit/presets/jira-branch
```

`<tag>` is a release that includes this preset (see [`presets/CHANGELOG.md`](../CHANGELOG.md)).
