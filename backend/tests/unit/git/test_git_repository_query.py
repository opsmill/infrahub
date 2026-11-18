from infrahub.git.graphql_queries import GitRepositoryNodeQuery, StoredUserCheckQuery
from infrahub.git.models import GitRepoNode


class TestGitRepositoryNodeQuery:
    def test_render_query_contains_kind_and_fields(self) -> None:
        q = GitRepositoryNodeQuery()
        rendered = q.render_query()
        assert "CoreRepository" in rendered
        assert "id" in rendered
        assert "name" in rendered
        assert "location" in rendered

    def test_render_query_correct_structure(self) -> None:
        q = GitRepositoryNodeQuery()
        rendered = q.render_query()
        assert "GitFetchRepositories" in rendered
        assert "edges" in rendered
        assert "node" in rendered

    def test_parse_response_returns_repo_nodes(self) -> None:
        q = GitRepositoryNodeQuery()
        response = {
            "CoreRepository": {
                "edges": [
                    {
                        "node": {
                            "id": "abc-123",
                            "name": {"value": "repo-a"},
                            "location": {"value": "git@github.com:a/a.git"},
                        }
                    },
                    {
                        "node": {
                            "id": "def-456",
                            "name": {"value": "repo-b"},
                            "location": {"value": "git@github.com:b/b.git"},
                        }
                    },
                ]
            }
        }
        result = q.parse_response(response=response)
        assert result == [
            GitRepoNode(id="abc-123", name="repo-a", location="git@github.com:a/a.git"),
            GitRepoNode(id="def-456", name="repo-b", location="git@github.com:b/b.git"),
        ]

    def test_parse_response_empty_edges(self) -> None:
        q = GitRepositoryNodeQuery()
        assert q.parse_response(response={"CoreRepository": {"edges": []}}) == []

    def test_parse_response_missing_kind_key(self) -> None:
        q = GitRepositoryNodeQuery()
        assert q.parse_response(response={}) == []

    def test_parse_response_skips_nodes_with_missing_fields(self) -> None:
        q = GitRepositoryNodeQuery()
        response = {
            "CoreRepository": {
                "edges": [
                    {
                        "node": {
                            "id": "abc-123",
                            "name": {"value": "repo-a"},
                            "location": {"value": "git@github.com:a/a.git"},
                        }
                    },
                    {"node": {"id": "def-456"}},
                ]
            }
        }
        result = q.parse_response(response=response)
        assert result == [GitRepoNode(id="abc-123", name="repo-a", location="git@github.com:a/a.git")]


class TestStoredUserCheckQuery:
    def test_name_starting_with_dollar_is_sent_as_a_variable(self) -> None:
        q = StoredUserCheckQuery(validator_id="validator-1", name="$critical")
        assert "$critical" not in q.render_query()
        assert q.variables() == {"validator_id": "validator-1", "name": "$critical"}

    def test_parse_response_returns_stored_check_id(self) -> None:
        q = StoredUserCheckQuery(validator_id="validator-1", name="device-1")
        response = {"CoreStandardCheck": {"edges": [{"node": {"id": "check-1"}}]}}
        assert q.parse_response(response=response) == "check-1"

    def test_parse_response_without_stored_check(self) -> None:
        q = StoredUserCheckQuery(validator_id="validator-1", name="device-1")
        assert q.parse_response(response={"CoreStandardCheck": {"edges": []}}) is None
