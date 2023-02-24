"""Unit tests for the DiffElement class.

Copyright (c) 2020-2021 Network To Code, LLC <info@networktocode.com>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from diffsync.diff import DiffElement


def test_diff_element_empty():
    """Test the basic functionality of the DiffElement class when initialized and empty."""
    element = DiffElement("interface", "eth0", {"device_name": "device1", "name": "eth0"})

    assert element.type == "interface"
    assert element.name == "eth0"
    assert element.keys == {"device_name": "device1", "name": "eth0"}
    assert element.source_name == "source"
    assert element.dest_name == "dest"
    assert element.source_attrs is None
    assert element.dest_attrs is None
    assert not list(element.get_children())
    assert not element.has_diffs()
    assert not element.has_diffs(include_children=True)
    assert not element.has_diffs(include_children=False)
    assert element.get_attrs_keys() == []

    element2 = DiffElement(
        "interface", "eth0", {"device_name": "device1", "name": "eth0"}, source_name="S1", dest_name="D1"
    )
    assert element2.source_name == "S1"
    assert element2.dest_name == "D1"


def test_diff_element_summary_with_no_diffs():
    element = DiffElement("interface", "eth0", {"device_name": "device1", "name": "eth0"})
    assert element.summary() == {"create": 0, "update": 0, "delete": 0, "no-change": 1}


def test_diff_element_str_with_no_diffs():
    element = DiffElement("interface", "eth0", {"device_name": "device1", "name": "eth0"})
    assert element.str() == "interface: eth0 (no diffs)"


def test_diff_element_dict_with_no_diffs():
    element = DiffElement("interface", "eth0", {"device_name": "device1", "name": "eth0"})
    assert not element.dict()


def test_diff_element_len_with_no_diffs():
    element = DiffElement("interface", "eth0", {"device_name": "device1", "name": "eth0"})
    assert len(element) == 1


def test_diff_element_attrs():
    """Test the basic functionality of the DiffElement class when setting and retrieving attrs."""
    element = DiffElement("interface", "eth0", {"device_name": "device1", "name": "eth0"})

    source_attrs = {"interface_type": "ethernet", "description": "my interface"}
    element.add_attrs(source=source_attrs)
    assert element.source_attrs == source_attrs

    assert element.has_diffs()
    assert element.has_diffs(include_children=True)
    assert element.has_diffs(include_children=False)
    assert element.get_attrs_keys() == source_attrs.keys()

    dest_attrs = {"description": "your interface"}
    element.add_attrs(dest=dest_attrs)
    assert element.source_attrs == source_attrs
    assert element.dest_attrs == dest_attrs

    assert element.has_diffs()
    assert element.has_diffs(include_children=True)
    assert element.has_diffs(include_children=False)
    assert element.get_attrs_keys() == ["description"]  # intersection of source_attrs.keys() and dest_attrs.keys()


def test_diff_element_summary_with_diffs():
    element = DiffElement("interface", "eth0", {"device_name": "device1", "name": "eth0"})
    element.add_attrs(source={"interface_type": "ethernet", "description": "my interface"})
    assert element.summary() == {"create": 1, "update": 0, "delete": 0, "no-change": 0}
    element.add_attrs(dest={"description": "your interface"})
    assert element.summary() == {"create": 0, "update": 1, "delete": 0, "no-change": 0}


def test_diff_element_str_with_diffs():
    element = DiffElement("interface", "eth0", {"device_name": "device1", "name": "eth0"})
    element.add_attrs(source={"interface_type": "ethernet", "description": "my interface"})
    assert element.str() == "interface: eth0 MISSING in dest"
    element.add_attrs(dest={"description": "your interface"})
    assert (
        element.str()
        == """\
interface: eth0
  description    source(my interface)    dest(your interface)\
"""
    )


def test_diff_element_dict_with_diffs():
    element = DiffElement("interface", "eth0", {"device_name": "device1", "name": "eth0"})
    element.add_attrs(source={"interface_type": "ethernet", "description": "my interface"})
    assert element.dict() == {"+": {"description": "my interface", "interface_type": "ethernet"}}
    element.add_attrs(dest={"description": "your interface"})
    assert element.dict() == {"-": {"description": "your interface"}, "+": {"description": "my interface"}}


def test_diff_element_len_with_diffs():
    element = DiffElement("interface", "eth0", {"device_name": "device1", "name": "eth0"})
    element.add_attrs(source={"interface_type": "ethernet", "description": "my interface"})
    element.add_attrs(dest={"description": "your interface"})
    assert len(element) == 1


def test_diff_element_dict_with_diffs_no_attrs():
    element = DiffElement("interface", "eth0", {"device_name": "device1", "name": "eth0"})
    element.add_attrs(source={})
    assert element.dict() == {"+": {}}
    element.add_attrs(dest={})
    assert element.dict() == {"+": {}, "-": {}}


def test_diff_element_children():
    """Test the basic functionality of the DiffElement class when storing and retrieving child elements."""
    child_element = DiffElement("interface", "eth0", {"device_name": "device1", "name": "eth0"})
    parent_element = DiffElement("device", "device1", {"name": "device1"})

    parent_element.add_child(child_element)
    assert list(parent_element.get_children()) == [child_element]
    assert not parent_element.has_diffs()
    assert not parent_element.has_diffs(include_children=True)
    assert not parent_element.has_diffs(include_children=False)

    source_attrs = {"interface_type": "ethernet", "description": "my interface"}
    dest_attrs = {"description": "your interface"}
    child_element.add_attrs(source=source_attrs, dest=dest_attrs)

    assert parent_element.has_diffs()
    assert parent_element.has_diffs(include_children=True)
    assert not parent_element.has_diffs(include_children=False)


def test_diff_element_summary_with_child_diffs(diff_element_with_children):
    # create interface "lo0"
    # delete interface "lo1"
    # update device "device1" and interface "eth0"
    # no change to interface "lo100"
    assert diff_element_with_children.summary() == {"create": 1, "update": 2, "delete": 1, "no-change": 1}


def test_diff_element_str_with_child_diffs(diff_element_with_children):
    assert (
        diff_element_with_children.str()
        == """\
device: device1
  role    source(switch)    dest(router)
  interface
    interface: eth0
      description    source(my interface)    dest(your interface)
    interface: lo0 MISSING in dest
    interface: lo1 MISSING in source\
"""
    )


def test_diff_element_dict_with_child_diffs(diff_element_with_children):
    assert diff_element_with_children.dict() == {
        "-": {"role": "router"},
        "+": {"role": "switch"},
        "interface": {
            "eth0": {"-": {"description": "your interface"}, "+": {"description": "my interface"}},
            "lo0": {"+": {}},
            "lo1": {"-": {"description": "Loopback 1"}},
        },
    }


def test_diff_element_len_with_child_diffs(diff_element_with_children):
    assert len(diff_element_with_children) == 5
    assert len(diff_element_with_children) == sum(count for count in diff_element_with_children.summary().values())
