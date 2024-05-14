from ipaddress import ip_interface, ip_network

from netaddr import IPNetwork

from infrahub.pools.address import get_available


def test_get_available():
    network = ip_network("10.16.18.0/30")
    addresses = [ip_interface("10.16.18.1/30")]
    available = get_available(network=network, addresses=addresses, is_pool=False)
    assert len(available) == 1
    assert available.iter_cidrs()[0] == IPNetwork("10.16.18.2/32")


def test_get_available_pool():
    network = ip_network("10.16.18.0/30")
    addresses = [ip_interface("10.16.18.1/30")]
    available = get_available(network=network, addresses=addresses, is_pool=True)
    assert len(available) == 3
    assert available.iter_cidrs()[0] == IPNetwork("10.16.18.0/32")
    assert available.iter_cidrs()[1] == IPNetwork("10.16.18.2/31")


def test_get_available_full():
    network = ip_network("10.16.18.0/30")
    addresses = [ip_interface("10.16.18.1/30"), ip_interface("10.16.18.2/30")]
    available = get_available(network=network, addresses=addresses, is_pool=False)
    assert len(available) == 0
