from infrahub.task_manager.flow_run.count import FlowRunCounter

CACHE_KEY_PREFIX = "task_manager:flow_run_count:"


class TestBuildCacheKey:
    def test_is_deterministic_for_the_same_body(self) -> None:
        body = {"flows": {"name": ["a"]}, "flow_runs": None}

        assert FlowRunCounter._build_cache_key(body) == FlowRunCounter._build_cache_key(body)

    def test_is_independent_of_key_order(self) -> None:
        first = FlowRunCounter._build_cache_key({"flows": None, "flow_runs": {"tags": ["x"]}})
        second = FlowRunCounter._build_cache_key({"flow_runs": {"tags": ["x"]}, "flows": None})

        assert first == second

    def test_differs_for_different_bodies(self) -> None:
        first = FlowRunCounter._build_cache_key({"flows": {"name": ["a"]}, "flow_runs": None})
        second = FlowRunCounter._build_cache_key({"flows": {"name": ["b"]}, "flow_runs": None})

        assert first != second

    def test_has_prefix_and_sha256_digest(self) -> None:
        key = FlowRunCounter._build_cache_key({"flows": None, "flow_runs": None})

        assert key.startswith(CACHE_KEY_PREFIX)
        digest = key.removeprefix(CACHE_KEY_PREFIX)
        assert len(digest) == 64
        assert all(char in "0123456789abcdef" for char in digest)
