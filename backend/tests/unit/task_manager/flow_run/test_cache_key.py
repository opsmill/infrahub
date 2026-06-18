from infrahub.task_manager.flow_run.cache_key import FlowRunCountCacheKeyBuilder

CACHE_KEY_PREFIX = "task_manager:flow_run_count:"


class TestFlowRunCountCacheKeyBuilder:
    def test_is_deterministic_for_the_same_body(self) -> None:
        builder = FlowRunCountCacheKeyBuilder()
        body = {"flows": {"name": ["a"]}, "flow_runs": None}

        assert builder.build(body) == builder.build(body)

    def test_is_independent_of_key_order(self) -> None:
        builder = FlowRunCountCacheKeyBuilder()
        first = builder.build({"flows": None, "flow_runs": {"tags": ["x"]}})
        second = builder.build({"flow_runs": {"tags": ["x"]}, "flows": None})

        assert first == second

    def test_differs_for_different_bodies(self) -> None:
        builder = FlowRunCountCacheKeyBuilder()
        first = builder.build({"flows": {"name": ["a"]}, "flow_runs": None})
        second = builder.build({"flows": {"name": ["b"]}, "flow_runs": None})

        assert first != second

    def test_has_prefix_and_sha256_digest(self) -> None:
        key = FlowRunCountCacheKeyBuilder().build({"flows": None, "flow_runs": None})

        assert key.startswith(CACHE_KEY_PREFIX)
        digest = key.removeprefix(CACHE_KEY_PREFIX)
        assert len(digest) == 64
        assert all(char in "0123456789abcdef" for char in digest)
