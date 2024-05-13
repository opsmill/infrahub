import ipaddress

import pytest

from infrahub.pools.prefix import PrefixPool


def test_init_v4():
    sub = PrefixPool("192.168.0.0/28")
    avail_subs = sub.get_nbr_available_subnets()

    assert avail_subs == {29: 2, 30: 0, 31: 0, 32: 0}
    assert sub.available_subnets[29] == ["192.168.0.0/29", "192.168.0.8/29"]


def test_init_v6():
    sub = PrefixPool("2001:db8::0/48")
    avail_subs = sub.get_nbr_available_subnets()

    assert avail_subs[49] == 2
    assert avail_subs[50] == 0


def test_split_supernet_first():
    sub = PrefixPool("192.168.0.0/24")

    sub.split_supernet(
        supernet=ipaddress.ip_network("192.168.0.128/25"),
        subnet=ipaddress.ip_network("192.168.0.128/27"),
    )
    avail_subs = sub.get_nbr_available_subnets()

    assert avail_subs[25] == 1
    assert avail_subs[26] == 1
    assert avail_subs[27] == 2
    assert avail_subs[28] == 0

    assert sub.available_subnets[25] == ["192.168.0.0/25"]
    assert sub.available_subnets[26] == ["192.168.0.192/26"]
    assert sub.available_subnets[27] == ["192.168.0.128/27", "192.168.0.160/27"]


def test_split_supernet_middle():
    sub = PrefixPool("192.168.0.0/24")

    sub.split_supernet(
        supernet=ipaddress.ip_network("192.168.0.128/25"),
        subnet=ipaddress.ip_network("192.168.0.192/27"),
    )
    avail_subs = sub.get_nbr_available_subnets()

    assert avail_subs[25] == 1
    assert avail_subs[26] == 1
    assert avail_subs[27] == 2
    assert avail_subs[28] == 0

    assert sub.available_subnets[25] == ["192.168.0.0/25"]
    assert sub.available_subnets[26] == ["192.168.0.128/26"]
    assert sub.available_subnets[27] == ["192.168.0.192/27", "192.168.0.224/27"]


def test_split_supernet_end():
    sub = PrefixPool("192.168.0.0/16")

    sub.split_supernet(
        supernet=ipaddress.ip_network("192.168.128.0/17"),
        subnet=ipaddress.ip_network("192.168.255.192/27"),
    )
    avail_subs = sub.get_nbr_available_subnets()

    assert avail_subs[17] == 1
    assert avail_subs[25] == 1
    assert avail_subs[26] == 1
    assert avail_subs[27] == 2
    assert avail_subs[28] == 0

    assert sub.available_subnets[17] == ["192.168.0.0/17"]
    assert sub.available_subnets[26] == ["192.168.255.128/26"]
    assert sub.available_subnets[27] == ["192.168.255.192/27", "192.168.255.224/27"]


def test_get_subnet_v4_no_owner():
    sub = PrefixPool("192.168.0.0/16")

    assert str(sub.get(size=24)) == "192.168.0.0/24"
    assert str(sub.get(size=25)) == "192.168.1.0/25"
    assert str(sub.get(size=17)) == "192.168.128.0/17"
    assert str(sub.get(size=24)) == "192.168.2.0/24"
    assert str(sub.get(size=25)) == "192.168.1.128/25"


def test_get_subnet_v4_with_owner():
    sub = PrefixPool("192.168.0.0/16")

    assert str(sub.get(size=24, identifier="first")) == "192.168.0.0/24"
    assert str(sub.get(size=25, identifier="second")) == "192.168.1.0/25"
    assert str(sub.get(size=17, identifier="third")) == "192.168.128.0/17"
    assert str(sub.get(size=25, identifier="second")) == "192.168.1.0/25"
    assert str(sub.get(size=17, identifier="third")) == "192.168.128.0/17"


def test_get_subnet_no_more_subnet():
    sub = PrefixPool("192.0.0.0/22")

    assert str(sub.get(size=24)) == "192.0.0.0/24"
    assert str(sub.get(size=24)) == "192.0.1.0/24"
    assert str(sub.get(size=24)) == "192.0.2.0/24"
    assert str(sub.get(size=24)) == "192.0.3.0/24"
    with pytest.raises(IndexError):
        assert sub.get(size=24) is False


def test_get_subnet_v6_no_owner():
    sub = PrefixPool("2620:135:6000:fffe::/64")
    assert str(sub.get(size=127)), "2620:135:6000:fffe::/127"


def test_already_allocated_v4_no_owner():
    sub = PrefixPool("192.168.0.0/16")

    assert str(sub.get(size=24, identifier="first")) == "192.168.0.0/24"
    assert str(sub.get(size=24, identifier="second")) == "192.168.1.0/24"

    assert sub.check_if_already_allocated(identifier="second") is True
    assert sub.check_if_already_allocated(identifier="third") is False


def test_reserve_no_owner():
    sub = PrefixPool("192.168.0.0/16")

    assert sub.reserve("192.168.0.0/24") is True
    assert str(sub.get(size=24)) == "192.168.1.0/24"


def test_reserve_wrong_input():
    sub = PrefixPool("192.168.0.0/16")

    with pytest.raises(ValueError):
        assert sub.reserve("192.192.1.0/24", identifier="first")


def test_reserve_with_owner():
    sub = PrefixPool("192.192.0.0/16")

    assert sub.reserve("192.192.0.0/24", identifier="first") is True
    assert sub.reserve("192.192.1.0/24", identifier="second") is True

    assert str(sub.get(size=24)) == "192.192.2.0/24"
