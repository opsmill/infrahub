import ipaddress

import pytest

from infrahub.core.utils import convert_ip_to_binary_str


@pytest.mark.parametrize(
    "input,response",
    [
        (ipaddress.ip_network("10.10.0.0/22"), "00001010000010100000000000000000"),
        (ipaddress.ip_interface("10.10.22.23/22"), "00001010000010100001011000010111"),
        (ipaddress.ip_interface("192.0.22.23/22"), "11000000000000000001011000010111"),
    ],
)
def test_convert_ip_to_binary_str(input, response):
    assert convert_ip_to_binary_str(obj=input) == response
