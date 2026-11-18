# critique-opsmill

Overrides `speckit.critique.run` from the [spec-kit-critique](https://github.com/arunt14/spec-kit-critique) extension, whose command looks for `check-prerequisites.sh` in the extension's folder, where it does not exist. The command is upstream `commands/run.md` at `v1.0.0`, with its script paths changed to `../../scripts/` and its report template found where the extension installs it. `speckit.opsmill.prep` runs it as its critique step.

## Install

Install the `critique` extension first, otherwise the override is skipped:

```bash
specify extension add critique \
  --from https://github.com/arunt14/spec-kit-critique/archive/refs/tags/v1.0.0.zip
git clone -b <tag> https://github.com/opsmill/opsmill-speckit
specify preset add --dev opsmill-speckit/presets/critique-opsmill
```

`<tag>` is a release that includes this preset (see [`presets/CHANGELOG.md`](../CHANGELOG.md)). If the preset was added before the extension, run `specify preset remove critique-opsmill` and add it again.

## License

MIT, from spec-kit-critique: see [`LICENSE`](LICENSE).
