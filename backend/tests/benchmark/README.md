
# Performance Benchmark with pytest-benchmark

The tests in this directory are performance benchmark designed to work with [`pytest-benchmark`](https://github.com/ionelmc/pytest-benchmark)

## Run all the tests

You can run all the tests with the following command

```sh
INFRAHUB_LOG_LEVEL=CRITICAL pytest -v backend/tests/benchmark/test_schemabranch_process.py --dist=no --benchmark-group-by=name
```

- `pytest-benchmark` is not compatible with xdist which is enabled by default so it's important to disable xdist with `--dist=no`
- By default, `pytest-benchmark` will compare all the tests together which it's that useful if the tests are very different, the option `--benchmark-group-by=name` tells `pytest-benchmark` to group the tests by name instead.

### Compare results

During development, it can be interesting to compare the result of one test with the previous execution with a different code. The options `--benchmark-compare` & `--benchmark-autosave` will automatically save the result of the current execution and compare it with the previous one if available.

```sh
INFRAHUB_LOG_LEVEL=CRITICAL pytest -v backend/tests/benchmark/test_schemabranch_process.py --dist=no --benchmark-group-by=name --benchmark-compare --benchmark-autosave
```