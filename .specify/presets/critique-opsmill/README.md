# critique-opsmill

Overrides `speckit.critique.run` from the [spec-kit-critique](https://github.com/arunt14/spec-kit-critique) extension, whose command looks for `check-prerequisites.sh` in the extension's folder, where it does not exist. The command is upstream `commands/run.md` at `v1.0.0`, with its script paths changed to `../../scripts/` and its report template found where the extension installs it. `speckit.opsmill.prep` runs it as its critique step.

## Install

Installed by the `opsmill-sdd` bundle, which also installs the `critique` extension: see [Install](../../README.md#install) in the repo README.

## License

MIT, from spec-kit-critique: see [`LICENSE`](LICENSE).
