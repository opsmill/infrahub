from infrahub.core import protocols


def test_sanity_protocol_defined():
    assert getattr(protocols, "CoreNode")
