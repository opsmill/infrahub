from infrahub.git.models import GitRepoNode, GitRepositoryNodeQuery


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
