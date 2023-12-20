from transforms.openconfig import OCBGPNeighbors, OCInterfaces


async def test_oc_interfaces_standard(helper):
    data, response = helper.fixture_files(directory_name="oc_interfaces/test01")
    transform = OCInterfaces()
    assert await transform.transform(data=data) == response


async def test_oc_bgp_neighbors_standard(helper):
    data, response = helper.fixture_files(directory_name="oc_bgp_neighbors/test01")
    transform = OCBGPNeighbors()
    assert await transform.transform(data=data) == response
