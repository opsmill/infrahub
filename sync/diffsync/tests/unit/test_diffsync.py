"""Unit tests for the DiffSync class."""
# pylint: disable=too-many-lines

from unittest import mock

import pytest
from diffsync import DiffSync, DiffSyncModel
from diffsync.enum import DiffSyncFlags, DiffSyncModelFlags
from diffsync.exceptions import DiffClassMismatch, ObjectAlreadyExists, ObjectCrudException, ObjectNotFound

from .conftest import BackendA, Device, Interface, PersonA, Site, TrackedDiff


def test_diffsync_default_name_type(generic_diffsync):
    assert generic_diffsync.type == "DiffSync"
    assert generic_diffsync.name == "DiffSync"


def test_diffsync_generic_load_is_noop(generic_diffsync):
    generic_diffsync.load()
    assert generic_diffsync.count() == 0


def test_diffsync_dict_with_no_data(generic_diffsync):
    assert generic_diffsync.dict() == {}


def test_diffsync_str_with_no_data(generic_diffsync):
    assert generic_diffsync.str() == ""


def test_diffsync_len_with_no_data(generic_diffsync):
    assert len(generic_diffsync) == 0


def test_diffsync_diff_self_with_no_data_has_no_diffs(generic_diffsync):
    assert generic_diffsync.diff_from(generic_diffsync).has_diffs() is False
    assert generic_diffsync.diff_to(generic_diffsync).has_diffs() is False


def test_diffsync_sync_self_with_no_data_is_noop(generic_diffsync):
    generic_diffsync.sync_complete = mock.Mock()
    generic_diffsync.sync_from(generic_diffsync)
    diff = generic_diffsync.sync_to(generic_diffsync)
    # Check if the returning Diff object has diffs
    assert not diff.has_diffs()
    # sync_complete() should only be called if something actually changed
    assert not generic_diffsync.sync_complete.called


def test_diffsync_get_with_no_data_fails(generic_diffsync):
    with pytest.raises(ObjectNotFound):
        generic_diffsync.get("anything", "myname")
    with pytest.raises(ObjectNotFound):
        generic_diffsync.get(DiffSyncModel, "")


def test_diffsync_get_all_with_no_data_is_empty_list(generic_diffsync):
    assert not list(generic_diffsync.get_all("anything"))
    assert not list(generic_diffsync.get_all(DiffSyncModel))


def test_diffsync_get_by_uids_with_no_data(generic_diffsync):
    assert not generic_diffsync.get_by_uids([], "anything")
    assert not generic_diffsync.get_by_uids([], DiffSyncModel)
    with pytest.raises(ObjectNotFound):
        generic_diffsync.get_by_uids(["any", "another"], "anything")
    with pytest.raises(ObjectNotFound):
        generic_diffsync.get_by_uids(["any", "another"], DiffSyncModel)


def test_diffsync_add_no_raises_existing_same_object(generic_diffsync):
    person = PersonA(name="Mikhail Yohman")

    modelname = person.get_type()
    uid = person.get_unique_id()

    # First attempt at adding object
    generic_diffsync.add(person)
    assert modelname in generic_diffsync.get_all_model_names()
    assert any(uid == obj.get_unique_id() for obj in generic_diffsync.get_all(modelname))

    assert person == generic_diffsync.get(modelname, uid)

    # Attempt to add again and make sure it doesn't raise an exception
    generic_diffsync.add(person)
    assert person is generic_diffsync.get(modelname, uid)
    assert person is generic_diffsync.get(PersonA, "Mikhail Yohman")


def test_diffsync_add_raises_already_exists_with_updated_object(generic_diffsync):
    intf = Interface(device_name="device1", name="eth0")
    # A DiffSync can store arbitrary DiffSyncModel objects, even if it doesn't know about them at definition time.
    generic_diffsync.add(intf)
    # Create new interface with same identifiers so it's technically the same object, but set additional attribute
    new_intf = Interface(device_name="device1", name="eth0", interface_type="1000base-t")
    with pytest.raises(ObjectAlreadyExists) as error:
        generic_diffsync.add(new_intf)
    error_model = error.value.existing_object
    assert isinstance(error_model, DiffSyncModel)
    assert new_intf is error_model


def test_diffsync_get_or_instantiate_create_non_existent_object(generic_diffsync):
    generic_diffsync.interface = Interface
    intf_identifiers = {"device_name": "device1", "name": "eth1"}

    # Assert that the object does not currently exist.
    with pytest.raises(ObjectNotFound):
        generic_diffsync.get(Interface, intf_identifiers)

    obj, created = generic_diffsync.get_or_instantiate(Interface, intf_identifiers)
    assert created
    assert obj is generic_diffsync.get(Interface, intf_identifiers)
    assert obj is generic_diffsync.get("interface", intf_identifiers)


def test_diffsync_get_or_instantiate_retrieve_existing_object(generic_diffsync):
    intf_identifiers = {"device_name": "device1", "name": "eth1"}
    intf = Interface(**intf_identifiers)
    generic_diffsync.add(intf)

    obj, created = generic_diffsync.get_or_instantiate(Interface, intf_identifiers)
    assert obj is intf
    assert not created


def test_diffsync_get_or_instantiate_retrieve_existing_object_w_attrs(generic_diffsync):
    intf_identifiers = {"device_name": "device1", "name": "eth1"}
    intf_attrs = {"interface_type": "1000base-t", "description": "Testing"}
    intf = Interface(**intf_identifiers)
    generic_diffsync.add(intf)

    obj, created = generic_diffsync.get_or_instantiate(Interface, intf_identifiers, intf_attrs)
    assert obj is intf
    assert not created
    assert obj.interface_type == "ethernet"
    assert obj.description is None


def test_diffsync_get_or_instantiate_retrieve_create_non_existent_w_attrs(generic_diffsync):
    generic_diffsync.interface = Interface
    intf_identifiers = {"device_name": "device1", "name": "eth1"}
    intf_attrs = {"interface_type": "1000base-t", "description": "Testing"}

    obj, created = generic_diffsync.get_or_instantiate(Interface, intf_identifiers, intf_attrs)
    assert created
    assert obj.interface_type == "1000base-t"
    assert obj.description == "Testing"
    assert obj is generic_diffsync.get(Interface, intf_identifiers)
    assert obj is generic_diffsync.get("interface", intf_identifiers)


def test_diffsync_get_or_instantiate_retrieve_existing_object_wo_attrs(generic_diffsync):
    intf_identifiers = {"device_name": "device1", "name": "eth1"}
    intf = Interface(**intf_identifiers)
    generic_diffsync.add(intf)

    obj, created = generic_diffsync.get_or_instantiate(Interface, intf_identifiers)
    assert obj is intf
    assert not created
    assert obj.interface_type == "ethernet"
    assert obj.description is None


def test_diffsync_get_or_add_model_instance_create_non_existent_object(generic_diffsync):
    generic_diffsync.interface = Interface
    intf_identifiers = {"device_name": "device1", "name": "eth1"}
    intf = generic_diffsync.interface(**intf_identifiers)

    # Assert that the object does not currently exist.
    with pytest.raises(ObjectNotFound):
        generic_diffsync.get(Interface, intf_identifiers)

    obj, created = generic_diffsync.get_or_add_model_instance(intf)
    assert created
    assert obj is generic_diffsync.get(Interface, intf_identifiers)
    assert obj is generic_diffsync.get("interface", intf_identifiers)


def test_diffsync_get_or_add_model_instance_retrieve_existing_object(generic_diffsync):
    intf_identifiers = {"device_name": "device1", "name": "eth1"}
    intf = Interface(**intf_identifiers)
    generic_diffsync.add(intf)

    obj, created = generic_diffsync.get_or_add_model_instance(intf)
    assert obj is intf
    assert not created


def test_diffsync_get_or_add_model_instance_retrieve_existing_object_w_attrs(generic_diffsync):
    intf_identifiers = {"device_name": "device1", "name": "eth1"}
    intf_attrs = {"interface_type": "ethernet"}
    intf_combine = {**intf_identifiers, **intf_attrs}
    intf = Interface(**intf_combine)
    generic_diffsync.add(intf)

    obj, created = generic_diffsync.get_or_add_model_instance(intf)
    assert obj is intf
    assert not created
    assert obj.interface_type == "ethernet"
    assert obj.description is None


def test_diffsync_get_or_add_model_instance_retrieve_create_non_existent_w_attrs(generic_diffsync):
    generic_diffsync.interface = Interface
    intf_identifiers = {"device_name": "device1", "name": "eth1"}
    intf_attrs = {"interface_type": "1000base-t", "description": "Testing"}
    intf_combine = {**intf_identifiers, **intf_attrs}
    intf = Interface(**intf_combine)

    obj, created = generic_diffsync.get_or_add_model_instance(intf)
    assert created
    assert obj.interface_type == "1000base-t"
    assert obj.description == "Testing"
    assert obj is generic_diffsync.get(Interface, intf_identifiers)
    assert obj is generic_diffsync.get("interface", intf_identifiers)


def test_diffsync_get_or_add_model_instance_retrieve_existing_object_wo_attrs(generic_diffsync):
    intf_identifiers = {"device_name": "device1", "name": "eth1"}
    intf = Interface(**intf_identifiers)
    generic_diffsync.add(intf)

    obj, created = generic_diffsync.get_or_add_model_instance(intf)
    assert obj is intf
    assert not created
    assert obj.interface_type == "ethernet"
    assert obj.description is None


def test_diffsync_update_or_instantiate_retrieve_existing_object_w_updated_attrs(generic_diffsync):
    intf_identifiers = {"device_name": "device1", "name": "eth1"}
    intf_attrs = {"interface_type": "1000base-t", "description": "Testing"}
    intf = Interface(**intf_identifiers)
    generic_diffsync.add(intf)

    obj, created = generic_diffsync.update_or_instantiate(Interface, intf_identifiers, intf_attrs)
    assert obj is intf
    assert not created
    assert obj.interface_type == "1000base-t"
    assert obj.description == "Testing"


def test_diffsync_update_or_instantiate_create_object(generic_diffsync):
    intf_identifiers = {"device_name": "device1", "name": "eth1"}

    obj, created = generic_diffsync.update_or_instantiate(Interface, intf_identifiers, {})
    assert created
    assert obj.interface_type == "ethernet"
    assert obj.description is None


def test_diffsync_update_or_instantiate_create_object_w_attrs(generic_diffsync):
    intf_identifiers = {"device_name": "device1", "name": "eth1"}
    intf_attrs = {"interface_type": "1000base-t", "description": "Testing"}

    obj, created = generic_diffsync.update_or_instantiate(Interface, intf_identifiers, intf_attrs)
    assert created
    assert obj.interface_type == "1000base-t"
    assert obj.description == "Testing"


def test_diffsync_update_or_add_model_instance_retrieve_existing_object_w_updated_attrs(generic_diffsync):
    intf_identifiers = {"device_name": "device1", "name": "eth1"}
    intf_attrs = {"interface_type": "1000base-t", "description": "Testing"}
    intf_combine = {**intf_identifiers, **intf_attrs}
    intf = Interface(**intf_combine)
    generic_diffsync.add(intf)

    obj, created = generic_diffsync.update_or_add_model_instance(intf)
    assert obj is intf
    assert not created
    assert obj.interface_type == "1000base-t"
    assert obj.description == "Testing"


def test_diffsync_update_or_add_model_instance_create_object(generic_diffsync):
    intf_identifiers = {"device_name": "device1", "name": "eth1"}
    intf = Interface(**intf_identifiers)

    obj, created = generic_diffsync.update_or_add_model_instance(intf)
    assert created
    assert obj.interface_type == "ethernet"
    assert obj.description is None


def test_diffsync_update_or_add_model_instance_create_object_w_attrs(generic_diffsync):
    intf_identifiers = {"device_name": "device1", "name": "eth1"}
    intf_attrs = {"interface_type": "1000base-t", "description": "Testing"}
    intf_combine = {**intf_identifiers, **intf_attrs}
    intf = Interface(**intf_combine)

    obj, created = generic_diffsync.update_or_add_model_instance(intf)
    assert created
    assert obj.interface_type == "1000base-t"
    assert obj.description == "Testing"


def test_diffsync_get_with_generic_model(generic_diffsync, generic_diffsync_model):
    generic_diffsync.add(generic_diffsync_model)
    # The generic_diffsync_model has an empty identifier/unique-id
    assert generic_diffsync.get(DiffSyncModel, "") == generic_diffsync_model
    assert generic_diffsync.get(DiffSyncModel.get_type(), "") == generic_diffsync_model
    # DiffSync doesn't know how to construct a uid str for a "diffsyncmodel" (it needs the class or instance, not a str)
    with pytest.raises(ValueError):
        generic_diffsync.get(DiffSyncModel.get_type(), {})
    # Wrong object-type - no match
    with pytest.raises(ObjectNotFound):
        generic_diffsync.get("", "")
    # Wrong unique-id - no match
    with pytest.raises(ObjectNotFound):
        generic_diffsync.get(DiffSyncModel, "myname")


def test_diffsync_get_all_with_generic_model(generic_diffsync, generic_diffsync_model):
    generic_diffsync.add(generic_diffsync_model)
    assert list(generic_diffsync.get_all(DiffSyncModel)) == [generic_diffsync_model]
    assert list(generic_diffsync.get_all(DiffSyncModel.get_type())) == [generic_diffsync_model]
    # Wrong object-type - no match
    assert not list(generic_diffsync.get_all("anything"))


def test_diffsync_get_by_uids_with_generic_model(generic_diffsync, generic_diffsync_model):
    generic_diffsync.add(generic_diffsync_model)
    assert generic_diffsync.get_by_uids([""], DiffSyncModel) == [generic_diffsync_model]
    assert generic_diffsync.get_by_uids([""], DiffSyncModel.get_type()) == [generic_diffsync_model]
    # Wrong unique-id - no match
    with pytest.raises(ObjectNotFound):
        generic_diffsync.get_by_uids(["myname"], DiffSyncModel)
    # Valid unique-id mixed in with unknown ones
    with pytest.raises(ObjectNotFound):
        generic_diffsync.get_by_uids(["aname", "", "anothername"], DiffSyncModel)


def test_diffsync_remove_with_generic_model(generic_diffsync, generic_diffsync_model):
    generic_diffsync.add(generic_diffsync_model)
    generic_diffsync.remove(generic_diffsync_model)
    with pytest.raises(ObjectNotFound):
        generic_diffsync.remove(generic_diffsync_model)

    with pytest.raises(ObjectNotFound):
        generic_diffsync.get(DiffSyncModel, "")
    assert not list(generic_diffsync.get_all(DiffSyncModel))
    with pytest.raises(ObjectNotFound):
        generic_diffsync.get_by_uids([""], DiffSyncModel)


def test_diffsync_subclass_validation_name_mismatch():
    # pylint: disable=unused-variable
    with pytest.raises(AttributeError) as excinfo:

        class BadElementName(DiffSync):
            """DiffSync with a DiffSyncModel attribute whose name does not match the modelname."""

            dev_class = Device  # should be device = Device

    assert "Device" in str(excinfo.value)
    assert "device" in str(excinfo.value)
    assert "dev_class" in str(excinfo.value)


def test_diffsync_subclass_validation_missing_top_level():
    # pylint: disable=unused-variable
    with pytest.raises(AttributeError) as excinfo:

        class MissingTopLevel(DiffSync):
            """DiffSync whose top_level references an attribute that does not exist on the class."""

            top_level = ["missing"]

    assert "top_level" in str(excinfo.value)
    assert "missing" in str(excinfo.value)
    assert "is not a class attribute" in str(excinfo.value)


def test_diffsync_subclass_validation_top_level_not_diffsyncmodel():
    # pylint: disable=unused-variable
    with pytest.raises(AttributeError) as excinfo:

        class TopLevelNotDiffSyncModel(DiffSync):
            """DiffSync whose top_level references an attribute that is not a DiffSyncModel subclass."""

            age = 0
            top_level = ["age"]

    assert "top_level" in str(excinfo.value)
    assert "age" in str(excinfo.value)
    assert "is not a DiffSyncModel" in str(excinfo.value)


def test_diffsync_dict_with_data(backend_a):
    assert backend_a.dict() == {
        "device": {
            "nyc-spine1": {
                "interfaces": ["nyc-spine1__eth0", "nyc-spine1__eth1"],
                "name": "nyc-spine1",
                "role": "spine",
                "site_name": "nyc",
            },
            "nyc-spine2": {
                "interfaces": ["nyc-spine2__eth0", "nyc-spine2__eth1"],
                "name": "nyc-spine2",
                "role": "spine",
                "site_name": "nyc",
            },
            "rdu-spine1": {
                "interfaces": ["rdu-spine1__eth0", "rdu-spine1__eth1"],
                "name": "rdu-spine1",
                "role": "spine",
                "site_name": "rdu",
            },
            "rdu-spine2": {
                "interfaces": ["rdu-spine2__eth0", "rdu-spine2__eth1"],
                "name": "rdu-spine2",
                "role": "spine",
                "site_name": "rdu",
            },
            "sfo-spine1": {
                "interfaces": ["sfo-spine1__eth0", "sfo-spine1__eth1"],
                "name": "sfo-spine1",
                "role": "spine",
                "site_name": "sfo",
            },
            "sfo-spine2": {
                "interfaces": ["sfo-spine2__eth0", "sfo-spine2__eth1", "sfo-spine2__eth2"],
                "name": "sfo-spine2",
                "role": "spine",
                "site_name": "sfo",
            },
        },
        "interface": {
            "nyc-spine1__eth0": {"description": "Interface 0", "device_name": "nyc-spine1", "name": "eth0"},
            "nyc-spine1__eth1": {"description": "Interface 1", "device_name": "nyc-spine1", "name": "eth1"},
            "nyc-spine2__eth0": {"description": "Interface 0", "device_name": "nyc-spine2", "name": "eth0"},
            "nyc-spine2__eth1": {"description": "Interface 1", "device_name": "nyc-spine2", "name": "eth1"},
            "rdu-spine1__eth0": {"description": "Interface 0", "device_name": "rdu-spine1", "name": "eth0"},
            "rdu-spine1__eth1": {"description": "Interface 1", "device_name": "rdu-spine1", "name": "eth1"},
            "rdu-spine2__eth0": {"description": "Interface 0", "device_name": "rdu-spine2", "name": "eth0"},
            "rdu-spine2__eth1": {"description": "Interface 1", "device_name": "rdu-spine2", "name": "eth1"},
            "sfo-spine1__eth0": {"description": "Interface 0", "device_name": "sfo-spine1", "name": "eth0"},
            "sfo-spine1__eth1": {"description": "Interface 1", "device_name": "sfo-spine1", "name": "eth1"},
            "sfo-spine2__eth0": {"description": "TBD", "device_name": "sfo-spine2", "name": "eth0"},
            "sfo-spine2__eth1": {"description": "ddd", "device_name": "sfo-spine2", "name": "eth1"},
            "sfo-spine2__eth2": {"description": "Interface 2", "device_name": "sfo-spine2", "name": "eth2"},
        },
        "person": {"Glenn Matthews": {"name": "Glenn Matthews"}},
        "site": {
            "nyc": {"devices": ["nyc-spine1", "nyc-spine2"], "name": "nyc"},
            "rdu": {"devices": ["rdu-spine1", "rdu-spine2"], "name": "rdu", "people": ["Glenn Matthews"]},
            "sfo": {"devices": ["sfo-spine1", "sfo-spine2"], "name": "sfo"},
        },
    }


def test_diffsync_str_with_data(backend_a):
    assert (
        backend_a.str()
        == """\
site
  site: nyc: {}
    devices
      device: nyc-spine1: {'role': 'spine', 'tag': ''}
        interfaces
          interface: nyc-spine1__eth0: {'interface_type': 'ethernet', 'description': 'Interface 0'}
          interface: nyc-spine1__eth1: {'interface_type': 'ethernet', 'description': 'Interface 1'}
      device: nyc-spine2: {'role': 'spine', 'tag': ''}
        interfaces
          interface: nyc-spine2__eth0: {'interface_type': 'ethernet', 'description': 'Interface 0'}
          interface: nyc-spine2__eth1: {'interface_type': 'ethernet', 'description': 'Interface 1'}
    people: []
  site: sfo: {}
    devices
      device: sfo-spine1: {'role': 'spine', 'tag': ''}
        interfaces
          interface: sfo-spine1__eth0: {'interface_type': 'ethernet', 'description': 'Interface 0'}
          interface: sfo-spine1__eth1: {'interface_type': 'ethernet', 'description': 'Interface 1'}
      device: sfo-spine2: {'role': 'spine', 'tag': ''}
        interfaces
          interface: sfo-spine2__eth0: {'interface_type': 'ethernet', 'description': 'TBD'}
          interface: sfo-spine2__eth1: {'interface_type': 'ethernet', 'description': 'ddd'}
          interface: sfo-spine2__eth2: {'interface_type': 'ethernet', 'description': 'Interface 2'}
    people: []
  site: rdu: {}
    devices
      device: rdu-spine1: {'role': 'spine', 'tag': ''}
        interfaces
          interface: rdu-spine1__eth0: {'interface_type': 'ethernet', 'description': 'Interface 0'}
          interface: rdu-spine1__eth1: {'interface_type': 'ethernet', 'description': 'Interface 1'}
      device: rdu-spine2: {'role': 'spine', 'tag': ''}
        interfaces
          interface: rdu-spine2__eth0: {'interface_type': 'ethernet', 'description': 'Interface 0'}
          interface: rdu-spine2__eth1: {'interface_type': 'ethernet', 'description': 'Interface 1'}
    people
      person: Glenn Matthews: {}
unused: []\
"""
    )


def test_diffsync_len_with_data(backend_a):
    assert len(backend_a) == 23


def test_diffsync_diff_self_with_data_has_no_diffs(backend_a):
    # Self diff should always show no diffs!
    assert backend_a.diff_from(backend_a).has_diffs() is False
    assert backend_a.diff_to(backend_a).has_diffs() is False


def test_diffsync_diff_other_with_data_has_diffs(backend_a, backend_b):
    assert backend_a.diff_to(backend_b).has_diffs() is True
    assert backend_a.diff_from(backend_b).has_diffs() is True


def test_diffsync_diff_to_and_diff_from_are_symmetric(backend_a, backend_b):
    diff_ab = backend_a.diff_from(backend_b)
    diff_ba = backend_a.diff_to(backend_b)

    def check_diff_symmetry(diff1, diff2):
        """Recursively compare two Diffs to make sure they are equal and opposite to one another."""
        assert len(list(diff1.get_children())) == len(list(diff2.get_children()))
        for elem1, elem2 in zip(sorted(diff1.get_children()), sorted(diff2.get_children())):
            # Same basic properties
            assert elem1.type == elem2.type
            assert elem1.name == elem2.name
            assert elem1.keys == elem2.keys
            assert elem1.has_diffs() == elem2.has_diffs()
            # Opposite diffs, if any
            assert elem1.source_attrs == elem2.dest_attrs
            assert elem1.dest_attrs == elem2.source_attrs
            check_diff_symmetry(elem1.child_diff, elem2.child_diff)

    check_diff_symmetry(diff_ab, diff_ba)


def test_diffsync_diff_from_with_custom_diff_class(backend_a, backend_b):
    diff_ba = backend_a.diff_from(backend_b, diff_class=TrackedDiff)
    diff_children = diff_ba.get_children()

    assert isinstance(diff_ba, TrackedDiff)
    for child in diff_children:
        if child.child_diff:
            assert isinstance(child.child_diff, TrackedDiff)
    assert diff_ba.is_complete is True


def test_diffsync_diff_with_callback(backend_a, backend_b):
    last_value = {"current": 0, "total": 0}

    def callback(stage, current, total):
        assert stage == "diff"
        last_value["current"] = current
        last_value["total"] = total

    expected = len(backend_a) + len(backend_b)

    backend_a.diff_from(backend_b, callback=callback)
    assert last_value == {"current": expected, "total": expected}

    last_value = {"current": 0, "total": 0}
    backend_a.diff_to(backend_b, callback=callback)
    assert last_value == {"current": expected, "total": expected}


def test_diffsync_sync_to_w_different_diff_class_raises(backend_a, backend_b):
    diff = backend_b.diff_to(backend_a)
    with pytest.raises(DiffClassMismatch) as failure:
        backend_b.sync_to(backend_a, diff_class=TrackedDiff, diff=diff)
    assert failure.value.args[0] == "The provided diff's class (Diff) does not match the diff_class: TrackedDiff"


def test_diffsync_sync_to_w_diff_no_mocks(backend_a, backend_b):
    diff = backend_b.diff_to(backend_a)
    assert diff.has_diffs()
    # Perform full sync
    backend_b.sync_to(backend_a, diff=diff)
    # Assert there are no diffs after synchronization
    post_diff = backend_b.diff_to(backend_a)
    assert not post_diff.has_diffs()


def test_diffsync_sync_to_w_diff(backend_a, backend_b):
    diff = backend_b.diff_to(backend_a)
    assert diff.has_diffs()
    # Mock diff_from to make sure it's not called when passing in an existing diff
    backend_b.diff_from = mock.Mock()
    backend_b.diff_to = mock.Mock()
    backend_a.diff_from = mock.Mock()
    backend_a.diff_to = mock.Mock()
    # Perform full sync
    result_diff = backend_b.sync_to(backend_a, diff=diff)
    # Assert none of the diff methods have been called
    assert not backend_b.diff_from.called
    assert not backend_b.diff_to.called
    assert not backend_a.diff_from.called
    assert not backend_a.diff_to.called
    assert result_diff.has_diffs()


def test_diffsync_sync_from_w_diff(backend_a, backend_b):
    diff = backend_a.diff_from(backend_b)
    assert diff.has_diffs()
    # Mock diff_from to make sure it's not called when passing in an existing diff
    backend_a.diff_from = mock.Mock()
    backend_a.diff_to = mock.Mock()
    backend_b.diff_from = mock.Mock()
    backend_b.diff_to = mock.Mock()
    # Perform full sync
    backend_a.sync_from(backend_b, diff=diff)
    # Assert none of the diff methods have been called
    assert not backend_a.diff_from.called
    assert not backend_a.diff_to.called
    assert not backend_b.diff_from.called
    assert not backend_b.diff_to.called


def test_diffsync_sync_from(backend_a, backend_b):
    backend_a.sync_complete = mock.Mock()
    backend_b.sync_complete = mock.Mock()
    # Perform full sync
    backend_a.sync_from(backend_b)

    # backend_a was updated, backend_b was not
    assert backend_a.sync_complete.called
    assert not backend_b.sync_complete.called

    # Make sure the sync descended through the diff elements to their children
    assert backend_a.get(Device, "sfo-spine1").role == "leaf"  # was initially "spine"

    # site_nyc and site_sfo should be updated, site_atl should be created, site_rdu should be deleted
    site_nyc_a = backend_a.get(Site, "nyc")
    assert isinstance(site_nyc_a, Site)
    assert site_nyc_a.name == "nyc"
    site_sfo_a = backend_a.get("site", "sfo")
    assert isinstance(site_sfo_a, Site)
    assert site_sfo_a.name == "sfo"
    site_atl_a = backend_a.get("site", "atl")
    assert isinstance(site_atl_a, Site)
    assert site_atl_a.name == "atl"
    with pytest.raises(ObjectNotFound):
        backend_a.get(Site, "rdu")
    with pytest.raises(ObjectNotFound):
        backend_a.get("nothing", "")

    assert list(backend_a.get_all(Site)) == [site_nyc_a, site_sfo_a, site_atl_a]
    assert list(backend_a.get_all("site")) == [site_nyc_a, site_sfo_a, site_atl_a]
    assert not list(backend_a.get_all("nothing"))

    assert backend_a.get_by_uids(["nyc", "sfo"], Site) == [site_nyc_a, site_sfo_a]
    assert backend_a.get_by_uids(["sfo", "nyc"], "site") == [site_sfo_a, site_nyc_a]
    with pytest.raises(ObjectNotFound):
        backend_a.get_by_uids(["nyc", "sfo"], Device)
    with pytest.raises(ObjectNotFound):
        backend_a.get_by_uids(["nyc", "sfo"], "device")


def test_diffsync_sync_with_callback(backend_a, backend_b):
    last_value = {"current": 0, "total": 0}

    def callback(stage, current, total):
        assert stage in ("diff", "sync")
        last_value["current"] = current
        last_value["total"] = total

    expected = len(backend_a.diff_from(backend_b))

    backend_a.sync_from(backend_b, callback=callback)
    assert last_value == {"current": expected, "total": expected}


def check_successful_sync_log_sanity(log, src, dst, flags):
    """Given a successful sync, make sure the captured structlogs are correct at a high level."""
    # All logs generated during the sync should include the src, dst, and flags data
    for event in log.events:
        assert "src" in event and event["src"] == src
        assert "dst" in event and event["dst"] == dst
        assert "flags" in event and event["flags"] == flags

    # No warnings or errors should have been logged in a fully successful sync
    assert all(event["level"] == "debug" or event["level"] == "info" for event in log.events)

    # Logs for beginning and end of diff and sync should have been generated
    assert log.has("Beginning diff calculation", level="info")
    assert log.has("Diff calculation complete", level="info")
    assert log.has("Beginning sync", level="info")


def check_sync_logs_against_diff(diffsync, diff, log, errors_permitted=False):
    """Given a Diff, make sure the captured structlogs correctly correspond to its contents/actions."""
    for element in diff.get_children():
        # This is kinda gross, but needed since a DiffElement stores a shortname and keys, not a unique_id
        uid = getattr(diffsync, element.type).create_unique_id(**element.keys)

        elem_events = [
            event for event in log.events if event.get("model") == element.type and event.get("unique_id") == uid
        ]
        assert elem_events, f"No events for {element.type} {uid} in:\n{log.events}"
        num_events = len(elem_events)

        if element.action is None:
            assert num_events == 1, f"Wrong number of events for {element}: {elem_events}"
            assert {
                ("action", None),
                ("event", "No changes to apply; no action needed"),
                ("level", "debug"),
            } <= elem_events[0].items()
        else:
            # In case of an error, there will be a third log, warning that child elements will not be synced
            if errors_permitted:
                assert num_events in (2, 3), f"Wrong number of events for {element}: {elem_events}"
            else:
                assert num_events == 2, f"Wrong number of events for {element}: {elem_events}"
            begin_event, complete_event = elem_events[:2]

            assert {
                ("action", element.action),
                ("event", f"Attempting model {element.action}"),
                ("level", "debug"),
            } <= begin_event.items()
            # attrs_diffs dict is unhashable so we can't include it in the above set comparison
            assert "diffs" in begin_event and begin_event["diffs"] == element.get_attrs_diffs()
            assert "status" not in begin_event

            if not errors_permitted:
                assert complete_event["level"] == "info" and complete_event["status"] == "success", complete_event

            if complete_event["status"] == "success":
                assert {
                    ("action", element.action),
                    ("event", f"{element.action.title()}d successfully"),
                    ("level", "info"),
                    ("status", "success"),
                } <= complete_event.items()
            elif complete_event["status"] == "failure":
                assert {
                    ("action", element.action),
                    ("level", "warning"),
                    ("status", "failure"),
                } <= complete_event.items()
            else:
                assert {("action", element.action), ("level", "error"), ("status", "error")} <= complete_event.items()

            # attrs_diffs dict is unhashable so we can't include it in the above set comparison
            assert "diffs" in complete_event and complete_event["diffs"] == element.get_attrs_diffs()

            if num_events == 3:
                child_skip_warning = elem_events[-1]
                assert {
                    ("action", element.action),
                    ("event", "No object resulted from sync, will not process child objects."),
                    ("level", "warning"),
                } <= child_skip_warning.items()
                assert "status" not in child_skip_warning

        # Recurse into child diff if applicable
        if num_events < 3:  # i.e., no error happened
            check_sync_logs_against_diff(diffsync, element.child_diff, log, errors_permitted)


def test_diffsync_no_log_unchanged_by_default(log, backend_a):
    backend_a.sync_from(backend_a)

    # Make sure logs were accurately generated
    check_successful_sync_log_sanity(log, backend_a, backend_a, DiffSyncFlags.NONE)

    # Since there were no changes, and we didn't set LOG_UNCHANGED_RECORDS, there should be no "unchanged" logs
    assert not any(event for event in log.events if "action" in event)
    assert not any(event for event in log.events if "status" in event)


def test_diffsync_log_unchanged_even_if_no_changes_overall(log, backend_a):
    diff = backend_a.diff_from(backend_a)
    assert not diff.has_diffs()
    # Discard logs generated during diff calculation
    log.events = []

    backend_a.sync_from(backend_a, flags=DiffSyncFlags.LOG_UNCHANGED_RECORDS)

    # Make sure logs were accurately generated
    check_successful_sync_log_sanity(log, backend_a, backend_a, DiffSyncFlags.LOG_UNCHANGED_RECORDS)
    check_sync_logs_against_diff(backend_a, diff, log)


def test_diffsync_sync_from_successful_logging(log, backend_a, backend_b):
    diff = backend_a.diff_from(backend_b)
    # Discard logs generated during diff calculation
    log.events = []

    backend_a.sync_from(backend_b, flags=DiffSyncFlags.LOG_UNCHANGED_RECORDS)

    # Make sure logs were accurately generated
    check_successful_sync_log_sanity(log, backend_b, backend_a, DiffSyncFlags.LOG_UNCHANGED_RECORDS)
    check_sync_logs_against_diff(backend_a, diff, log)


def test_diffsync_subclass_default_name_type(backend_a):
    assert backend_a.name == "BackendA"
    assert backend_a.type == "BackendA"


def test_diffsync_subclass_custom_name_type(backend_b):
    assert backend_b.name == "backend-b"
    assert backend_b.type == "Backend_B"


def test_diffsync_add_get_remove_with_subclass_and_data(backend_a):
    site_nyc_a = backend_a.get(Site, "nyc")
    site_sfo_a = backend_a.get("site", "sfo")
    site_rdu_a = backend_a.get(Site, "rdu")
    site_atl_a = Site(name="atl")
    backend_a.add(site_atl_a)

    assert backend_a.get(Site, "atl") == site_atl_a
    assert list(backend_a.get_all("site")) == [site_nyc_a, site_sfo_a, site_rdu_a, site_atl_a]
    assert backend_a.get_by_uids(["rdu", "sfo", "atl", "nyc"], "site") == [
        site_rdu_a,
        site_sfo_a,
        site_atl_a,
        site_nyc_a,
    ]

    backend_a.remove(site_atl_a)
    with pytest.raises(ObjectNotFound):
        backend_a.remove(site_atl_a)


def test_diffsync_remove_missing_child(log, backend_a):
    rdu_spine1 = backend_a.get(Device, "rdu-spine1")
    rdu_spine1_eth0 = backend_a.get(Interface, "rdu-spine1__eth0")
    # Usage error - remove rdu_spine1_eth0 from backend_a, but rdu_spine1 still has a reference to it
    backend_a.remove(rdu_spine1_eth0)
    # Should log an error but continue removing other child objects
    backend_a.remove(rdu_spine1, remove_children=True)
    assert log.has(
        "Unable to remove child element as it was not found!",
        store=backend_a.store,
        parent_id=str(rdu_spine1),
        parent_type=rdu_spine1.get_type(),
        child_id=str(rdu_spine1_eth0),
        child_type=rdu_spine1_eth0.get_type(),
    )
    with pytest.raises(ObjectNotFound):
        backend_a.get(Interface, "rdu-spine1__eth1")


def test_diffsync_sync_from_exceptions_are_not_caught_by_default(error_prone_backend_a, backend_b):
    with pytest.raises(ObjectCrudException):
        error_prone_backend_a.sync_from(backend_b)


def test_diffsync_sync_from_with_continue_on_failure_flag(log, error_prone_backend_a, backend_b):
    base_diffs = error_prone_backend_a.diff_from(backend_b)
    log.events = []

    error_prone_backend_a.sync_from(
        backend_b, flags=DiffSyncFlags.CONTINUE_ON_FAILURE | DiffSyncFlags.LOG_UNCHANGED_RECORDS
    )
    # Not all sync operations succeeded on the first try
    remaining_diffs = error_prone_backend_a.diff_from(backend_b)
    print(remaining_diffs.str())  # for debugging of any failure
    assert remaining_diffs.has_diffs()

    # At least some operations of each type should have succeeded
    assert log.has("Created successfully", status="success")
    assert log.has("Updated successfully", status="success")
    assert log.has("Deleted successfully", status="success")
    # Some ERROR messages should have been logged
    assert [event for event in log.events if event["level"] == "error"] != []
    # Some messages with status="error" should have been logged - these may be the same as the above
    assert [event for event in log.events if event.get("status") == "error"] != []

    check_sync_logs_against_diff(error_prone_backend_a, base_diffs, log, errors_permitted=True)

    log.events = []

    # Retry up to 10 times, we should sync successfully eventually
    for i in range(10):
        print(f"Sync retry #{i}")
        error_prone_backend_a.sync_from(backend_b, flags=DiffSyncFlags.CONTINUE_ON_FAILURE)
        remaining_diffs = error_prone_backend_a.diff_from(backend_b)
        print(remaining_diffs.str())  # for debugging of any failure
        if remaining_diffs.has_diffs():
            # If we still have diffs, some ERROR messages should have been logged
            assert [event for event in log.events if event["level"] == "error"] != []
            # Some messages with status="errored" should have been logged - these may be the same as the above
            assert [event for event in log.events if event.get("status") == "error"] != []
            log.events = []
        else:
            # No error messages should have been logged on the last, fully successful attempt
            assert [event for event in log.events if event["level"] == "error"] == []
            # Something must have succeeded for us to be done
            assert [event for event in log.events if event.get("status") == "success"] != []
            break
    else:
        pytest.fail("Sync was still incomplete after 10 retries")


def test_diffsync_diff_with_skip_unmatched_src_flag(
    backend_a, backend_a_with_extra_models, backend_a_minus_some_models
):
    diff = backend_a.diff_from(backend_a_with_extra_models)
    assert diff.summary() == {"create": 2, "update": 0, "delete": 0, "no-change": 23, "skip": 0}

    # SKIP_UNMATCHED_SRC should mean that extra models in the src are not flagged for creation in the dest
    diff = backend_a.diff_from(backend_a_with_extra_models, flags=DiffSyncFlags.SKIP_UNMATCHED_SRC)
    assert diff.summary() == {"create": 0, "update": 0, "delete": 0, "no-change": 23, "skip": 2}

    # SKIP_UNMATCHED_SRC should NOT mean that extra models in the dst are not flagged for deletion in the src
    diff = backend_a.diff_from(backend_a_minus_some_models, flags=DiffSyncFlags.SKIP_UNMATCHED_SRC)
    assert diff.summary() == {"create": 0, "update": 0, "delete": 12, "no-change": 11, "skip": 0}


def test_diffsync_diff_with_skip_unmatched_dst_flag(
    backend_a, backend_a_with_extra_models, backend_a_minus_some_models
):
    diff = backend_a.diff_from(backend_a_minus_some_models)
    assert diff.summary() == {"create": 0, "update": 0, "delete": 12, "no-change": 11, "skip": 0}

    # SKIP_UNMATCHED_DST should mean that missing models in the src are not flagged for deletion from the dest
    diff = backend_a.diff_from(backend_a_minus_some_models, flags=DiffSyncFlags.SKIP_UNMATCHED_DST)
    assert diff.summary() == {"create": 0, "update": 0, "delete": 0, "no-change": 11, "skip": 2}

    # SKIP_UNMATCHED_DST should NOT mean that extra models in the src are not flagged for creation in the dest
    diff = backend_a.diff_from(backend_a_with_extra_models, flags=DiffSyncFlags.SKIP_UNMATCHED_DST)
    assert diff.summary() == {"create": 2, "update": 0, "delete": 0, "no-change": 23, "skip": 0}


def test_diffsync_diff_with_skip_unmatched_both_flag(
    backend_a, backend_a_with_extra_models, backend_a_minus_some_models
):
    # SKIP_UNMATCHED_BOTH should mean that extra models in the src are not flagged for creation in the dest
    diff = backend_a.diff_from(backend_a_with_extra_models, flags=DiffSyncFlags.SKIP_UNMATCHED_BOTH)
    assert diff.summary() == {"create": 0, "update": 0, "delete": 0, "no-change": 23, "skip": 2}

    # SKIP_UNMATCHED_BOTH should mean that missing models in the src are not flagged for deletion from the dest
    diff = backend_a.diff_from(backend_a_minus_some_models, flags=DiffSyncFlags.SKIP_UNMATCHED_BOTH)
    assert diff.summary() == {"create": 0, "update": 0, "delete": 0, "no-change": 11, "skip": 2}


def test_diffsync_sync_with_skip_unmatched_src_flag(backend_a, backend_a_with_extra_models):
    backend_a.sync_from(backend_a_with_extra_models, flags=DiffSyncFlags.SKIP_UNMATCHED_SRC)
    # New objects should not have been created
    with pytest.raises(ObjectNotFound):
        backend_a.get(backend_a.site, "lax")
    with pytest.raises(ObjectNotFound):
        backend_a.get(backend_a.device, "nyc-spine3")
    assert "nyc-spine3" not in backend_a.get(backend_a.site, "nyc").devices


def test_diffsync_sync_with_skip_unmatched_dst_flag(backend_a, backend_a_minus_some_models):
    backend_a.sync_from(backend_a_minus_some_models, flags=DiffSyncFlags.SKIP_UNMATCHED_DST)
    # Objects should not have been deleted
    assert backend_a.get(backend_a.site, "rdu") is not None
    assert backend_a.get(backend_a.device, "sfo-spine2") is not None
    assert "sfo-spine2" in backend_a.get(backend_a.site, "sfo").devices


def test_diffsync_sync_skip_children_on_delete(backend_a):
    class NoDeleteInterface(Interface):
        """Interface that shouldn't be deleted directly."""

        def delete(self):
            raise RuntimeError("Don't delete me, bro!")

    class NoDeleteInterfaceDiffSync(BackendA):
        """BackendA, but using NoDeleteInterface."""

        interface = NoDeleteInterface

    extra_models = NoDeleteInterfaceDiffSync()
    extra_models.load()
    extra_device = extra_models.device(name="nyc-spine3", site_name="nyc", role="spine")
    extra_device.model_flags |= DiffSyncModelFlags.SKIP_CHILDREN_ON_DELETE
    extra_models.get(extra_models.site, "nyc").add_child(extra_device)
    extra_models.add(extra_device)
    extra_interface = extra_models.interface(name="eth0", device_name="nyc-spine3")
    extra_device.add_child(extra_interface)
    extra_models.add(extra_interface)
    assert extra_models.get(extra_models.interface, "nyc-spine3__eth0") is not None

    # NoDeleteInterface.delete() should not be called since we're deleting its parent only
    extra_models.sync_from(backend_a)
    # The extra interface should have been removed from the DiffSync without calling its delete() method
    with pytest.raises(ObjectNotFound):
        extra_models.get(extra_models.interface, extra_interface.get_unique_id())
    # The sync should be complete, regardless
    diff = extra_models.diff_from(backend_a)
    print(diff.str())  # for debugging of any failure
    assert not diff.has_diffs()


def test_diffsync_tree_traversal():
    assert BackendA.get_tree_traversal(True) == {"site": {"device": {"interface": {}}, "person": {}}, "unused": {}}
    text = """\
BackendA
├── site
│   ├── device
│   │   └── interface
│   └── person
└── unused"""
    assert BackendA.get_tree_traversal() == text


def test_diffsync_load_from_dict(backend_a):
    data = {
        "device": {
            "nyc-spine1": {
                "interfaces": ["nyc-spine1__eth0", "nyc-spine1__eth1"],
                "name": "nyc-spine1",
                "role": "spine",
                "site_name": "nyc",
            },
            "nyc-spine2": {
                "interfaces": ["nyc-spine2__eth0", "nyc-spine2__eth1"],
                "name": "nyc-spine2",
                "role": "spine",
                "site_name": "nyc",
            },
            "rdu-spine1": {
                "interfaces": ["rdu-spine1__eth0", "rdu-spine1__eth1"],
                "name": "rdu-spine1",
                "role": "spine",
                "site_name": "rdu",
            },
            "rdu-spine2": {
                "interfaces": ["rdu-spine2__eth0", "rdu-spine2__eth1"],
                "name": "rdu-spine2",
                "role": "spine",
                "site_name": "rdu",
            },
            "sfo-spine1": {
                "interfaces": ["sfo-spine1__eth0", "sfo-spine1__eth1"],
                "name": "sfo-spine1",
                "role": "spine",
                "site_name": "sfo",
            },
            "sfo-spine2": {
                "interfaces": ["sfo-spine2__eth0", "sfo-spine2__eth1", "sfo-spine2__eth2"],
                "name": "sfo-spine2",
                "role": "spine",
                "site_name": "sfo",
            },
        },
        "interface": {
            "nyc-spine1__eth0": {
                "description": "Interface 0",
                "device_name": "nyc-spine1",
                "name": "eth0",
            },
            "nyc-spine1__eth1": {
                "description": "Interface 1",
                "device_name": "nyc-spine1",
                "name": "eth1",
            },
            "nyc-spine2__eth0": {
                "description": "Interface 0",
                "device_name": "nyc-spine2",
                "name": "eth0",
            },
            "nyc-spine2__eth1": {
                "description": "Interface 1",
                "device_name": "nyc-spine2",
                "name": "eth1",
            },
            "rdu-spine1__eth0": {
                "description": "Interface 0",
                "device_name": "rdu-spine1",
                "name": "eth0",
            },
            "rdu-spine1__eth1": {
                "description": "Interface 1",
                "device_name": "rdu-spine1",
                "name": "eth1",
            },
            "rdu-spine2__eth0": {
                "description": "Interface 0",
                "device_name": "rdu-spine2",
                "name": "eth0",
            },
            "rdu-spine2__eth1": {
                "description": "Interface 1",
                "device_name": "rdu-spine2",
                "name": "eth1",
            },
            "sfo-spine1__eth0": {
                "description": "Interface 0",
                "device_name": "sfo-spine1",
                "name": "eth0",
            },
            "sfo-spine1__eth1": {
                "description": "Interface 1",
                "device_name": "sfo-spine1",
                "name": "eth1",
            },
            "sfo-spine2__eth0": {
                "description": "TBD",
                "device_name": "sfo-spine2",
                "name": "eth0",
            },
            "sfo-spine2__eth1": {
                "description": "ddd",
                "device_name": "sfo-spine2",
                "name": "eth1",
            },
            "sfo-spine2__eth2": {
                "description": "Interface 2",
                "device_name": "sfo-spine2",
                "name": "eth2",
            },
        },
        "person": {"Glenn Matthews": {"name": "Glenn Matthews"}},
        "site": {
            "nyc": {"devices": ["nyc-spine1", "nyc-spine2"], "name": "nyc"},
            "rdu": {
                "devices": ["rdu-spine1", "rdu-spine2"],
                "name": "rdu",
                "people": ["Glenn Matthews"],
            },
            "sfo": {"devices": ["sfo-spine1", "sfo-spine2"], "name": "sfo"},
        },
    }
    backend_a_by_dict = BackendA()
    backend_a_by_dict.load_from_dict(data)
    assert backend_a.dict() == backend_a_by_dict.dict()


def test_diffsync_get_or_none(backend_a):
    assert backend_a.get_or_none(backend_a.site, "rdu") is not None
    assert backend_a.get_or_none(backend_a.site, "does-not-exist") is None


def test_diffsync_get_initial_value_order():
    assert BackendA._get_initial_value_order() == [  # pylint: disable=protected-access
        "site",
        "unused",
        "device",
        "interface",
        "person",
    ]
