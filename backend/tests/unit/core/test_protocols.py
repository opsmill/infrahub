from infrahub.core import protocols


def test_sanity_protocol_defined() -> None:
    assert hasattr(protocols, "CoreNode")
