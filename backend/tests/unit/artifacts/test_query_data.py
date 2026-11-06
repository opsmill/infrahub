from infrahub.artifacts.query_data import RenderedQueryData, fingerprint_query_data
from tests.adapters.cache import MemoryCache


def test_fingerprint_ignores_key_order_but_not_list_order() -> None:
    """The same data gives the same fingerprint whatever the order of its keys, and a reordered list does not."""
    data = {"data": {"device": {"name": "dev1", "color": "blue"}}}
    reordered_keys = {"data": {"device": {"color": "blue", "name": "dev1"}}}

    assert fingerprint_query_data(data) == "7f1cd3f291909d2d30f0b657d1c89f2d6d28fd1721e56fd7b27a6c75ea4a5d25"
    assert fingerprint_query_data(reordered_keys) == fingerprint_query_data(data)
    assert fingerprint_query_data({"data": {"names": ["a", "b"]}}) != fingerprint_query_data(
        {"data": {"names": ["b", "a"]}}
    )


async def test_fingerprints_are_kept_per_branch_and_artifact() -> None:
    """A fingerprint saved for an artifact on one branch is not returned for another branch, nor after it is removed."""
    rendered_query_data = RenderedQueryData(cache=MemoryCache())
    await rendered_query_data.save(branch_id="branch-1", artifact_id="artifact-1", fingerprint="from-red")
    await rendered_query_data.save(branch_id="branch-1", artifact_id="artifact-2", fingerprint="from-blue")
    await rendered_query_data.save(branch_id="branch-2", artifact_id="artifact-1", fingerprint="from-green")
    await rendered_query_data.forget(branch_id="branch-1", artifact_id="artifact-2")

    stored = await rendered_query_data.get_many(
        branch_id="branch-1", artifact_ids=["artifact-1", "artifact-2", "artifact-3"]
    )

    assert stored == {"artifact-1": "from-red", "artifact-2": None, "artifact-3": None}
