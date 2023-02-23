"""Diff and DiffElement classes for DiffSync.

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

from functools import total_ordering
from typing import Any, Iterator, Iterable, Mapping, Optional, Text, Type

from .exceptions import ObjectAlreadyExists
from .utils import intersection, OrderedDefaultDict
from .enum import DiffSyncActions


class Diff:
    """Diff Object, designed to store multiple DiffElement object and organize them in a group."""

    def __init__(self):
        """Initialize a new, empty Diff object."""
        self.children = OrderedDefaultDict(dict)
        """DefaultDict for storing DiffElement objects.

        `self.children[group][unique_id] == DiffElement(...)`
        """
        self.models_processed = 0

    def __len__(self):
        """Total number of DiffElements stored herein."""
        total = 0
        for child in self.get_children():
            total += len(child)
        return total

    def complete(self):
        """Method to call when this Diff has been fully populated with data and is "complete".

        The default implementation does nothing, but a subclass could use this, for example, to save
        the completed Diff to a file or database record.
        """

    def add(self, element: "DiffElement"):
        """Add a new DiffElement to the changeset of this Diff.

        Raises:
            ObjectAlreadyExists: if an element of the same type and same name is already stored.
        """
        # Note that element.name is usually a DiffSyncModel.shortname() -- i.e., NOT guaranteed globally unique!!
        if element.name in self.children[element.type]:
            raise ObjectAlreadyExists(f"Already storing a {element.type} named {element.name}", element)

        self.children[element.type][element.name] = element

    def groups(self):
        """Get the list of all group keys in self.children."""
        return self.children.keys()

    def has_diffs(self) -> bool:
        """Indicate if at least one of the child elements contains some diff.

        Returns:
            bool: True if at least one child element contains some diff
        """
        for group in self.groups():
            for child in self.children[group].values():
                if child.has_diffs(include_children=True):
                    return True

        return False

    def get_children(self) -> Iterator["DiffElement"]:
        """Iterate over all child elements in all groups in self.children.

        For each group of children, check if an order method is defined,
        Otherwise use the default method.
        """
        order_default = "order_children_default"

        for group in self.groups():
            order_method_name = f"order_children_{group}"
            if hasattr(self, order_method_name):
                order_method = getattr(self, order_method_name)
            else:
                order_method = getattr(self, order_default)

            yield from order_method(self.children[group])

    @classmethod
    def order_children_default(cls, children: Mapping) -> Iterator["DiffElement"]:
        """Default method to an Iterator for children.

        Since children is already an OrderedDefaultDict, this method is not doing anything special.
        """
        for child in children.values():
            yield child

    def summary(self) -> Mapping[Text, int]:
        """Build a dict summary of this Diff and its child DiffElements."""
        summary = {
            DiffSyncActions.CREATE: 0,
            DiffSyncActions.UPDATE: 0,
            DiffSyncActions.DELETE: 0,
            "no-change": 0,
        }
        for child in self.get_children():
            child_summary = child.summary()
            for key in summary:
                summary[key] += child_summary[key]
        summary[DiffSyncActions.SKIP] = (
            self.models_processed
            - summary[DiffSyncActions.CREATE]
            # Updated elements are doubly accumulated in models_processed as they exist in SCR and DST.
            - 2 * summary[DiffSyncActions.UPDATE]
            - summary[DiffSyncActions.DELETE]
            # 'no-change' elements are doubly accumulated in models_processed as they exist in SCR and DST.
            - 2 * summary["no-change"]
        )
        return summary

    def str(self, indent: int = 0):
        """Build a detailed string representation of this Diff and its child DiffElements."""
        margin = " " * indent
        output = []
        for group in self.groups():
            group_heading_added = False
            for child in self.children[group].values():
                if child.has_diffs(include_children=True):
                    if not group_heading_added:
                        output.append(f"{margin}{group}")
                        group_heading_added = True
                    output.append(child.str(indent + 2))
        result = "\n".join(output)
        if not result:
            result = "(no diffs)"
        return result

    def dict(self) -> Mapping[Text, Mapping[Text, Mapping]]:
        """Build a dictionary representation of this Diff."""
        result = OrderedDefaultDict(dict)
        for child in self.get_children():
            if child.has_diffs(include_children=True):
                result[child.type][child.name] = child.dict()
        return dict(result)


@total_ordering
class DiffElement:  # pylint: disable=too-many-instance-attributes
    """DiffElement object, designed to represent a single item/object that may or may not have any diffs."""

    def __init__(
        self,
        obj_type: Text,
        name: Text,
        keys: Mapping,
        source_name: Text = "source",
        dest_name: Text = "dest",
        diff_class: Type[Diff] = Diff,
    ):  # pylint: disable=too-many-arguments
        """Instantiate a DiffElement.

        Args:
            obj_type: Name of the object type being described, as in DiffSyncModel.get_type().
            name: Human-readable name of the object being described, as in DiffSyncModel.get_shortname().
                This name must be unique within the context of the Diff that is the direct parent of this DiffElement.
            keys: Primary keys and values uniquely describing this object, as in DiffSyncModel.get_identifiers().
            source_name: Name of the source DiffSync object
            dest_name: Name of the destination DiffSync object
            diff_class: Diff or subclass thereof to use to calculate the diffs to use for synchronization
        """
        if not isinstance(obj_type, str):
            raise ValueError(f"obj_type must be a string (not {type(obj_type)})")

        if not isinstance(name, str):
            raise ValueError(f"name must be a string (not {type(name)})")

        self.type = obj_type
        self.name = name
        self.keys = keys
        self.source_name = source_name
        self.dest_name = dest_name
        # Note: *_attrs == None if no target object exists; it'll be an empty dict if it exists but has no _attributes
        self.source_attrs: Optional[Mapping] = None
        self.dest_attrs: Optional[Mapping] = None
        self.child_diff = diff_class()

    def __lt__(self, other):
        """Logical ordering of DiffElements.

        Other comparison methods (__gt__, __le__, __ge__, etc.) are created by our use of the @total_ordering decorator.
        """
        return (self.type, self.name) < (other.type, other.name)

    def __eq__(self, other):
        """Logical equality of DiffElements.

        Other comparison methods (__gt__, __le__, __ge__, etc.) are created by our use of the @total_ordering decorator.
        """
        if not isinstance(other, DiffElement):
            return NotImplemented
        return (
            self.type == other.type
            and self.name == other.name
            and self.keys == other.keys
            and self.source_attrs == other.source_attrs
            and self.dest_attrs == other.dest_attrs
            # TODO also check that self.child_diff == other.child_diff, needs Diff to implement __eq__().
        )

    def __str__(self):
        """Basic string representation of a DiffElement."""
        return (
            f'{self.type} "{self.name}" : {self.keys} : '
            f"{self.source_name} → {self.dest_name} : {self.get_attrs_diffs()}"
        )

    def __len__(self):
        """Total number of DiffElements in this one, including itself."""
        total = 1  # self
        for child in self.get_children():
            total += len(child)
        return total

    @property
    def action(self) -> Optional[Text]:
        """Action, if any, that should be taken to remediate the diffs described by this element.

        Returns:
            str: DiffSyncActions ("create", "update", "delete", or None)
        """
        if self.source_attrs is not None and self.dest_attrs is None:
            return DiffSyncActions.CREATE
        if self.source_attrs is None and self.dest_attrs is not None:
            return DiffSyncActions.DELETE
        if (
            self.source_attrs is not None
            and self.dest_attrs is not None
            and any(self.source_attrs[attr_key] != self.dest_attrs[attr_key] for attr_key in self.get_attrs_keys())
        ):
            return DiffSyncActions.UPDATE

        return None

    # TODO: separate into set_source_attrs() and set_dest_attrs() methods, or just use direct property access instead?
    def add_attrs(self, source: Optional[Mapping] = None, dest: Optional[Mapping] = None):
        """Set additional attributes of a source and/or destination item that may result in diffs."""
        # TODO: should source_attrs and dest_attrs be "write-once" properties, or is it OK to overwrite them once set?
        if source is not None:
            self.source_attrs = source

        if dest is not None:
            self.dest_attrs = dest

    def get_attrs_keys(self) -> Iterable[Text]:
        """Get the list of shared attrs between source and dest, or the attrs of source or dest if only one is present.

        - If source_attrs is not set, return the keys of dest_attrs
        - If dest_attrs is not set, return the keys of source_attrs
        - If both are defined, return the intersection of both keys
        """
        if self.source_attrs is not None and self.dest_attrs is not None:
            return intersection(self.dest_attrs.keys(), self.source_attrs.keys())
        if self.source_attrs is None and self.dest_attrs is not None:
            return self.dest_attrs.keys()
        if self.source_attrs is not None and self.dest_attrs is None:
            return self.source_attrs.keys()
        return []

    def get_attrs_diffs(self) -> Mapping[Text, Mapping[Text, Any]]:
        """Get the dict of actual attribute diffs between source_attrs and dest_attrs.

        Returns:
            dict: of the form `{"-": {key1: <value>, key2: ...}, "+": {key1: <value>, key2: ...}}`,
            where the `"-"` or `"+"` dicts may be absent.
        """
        if self.source_attrs is not None and self.dest_attrs is not None:
            return {
                "-": {
                    key: self.dest_attrs[key]
                    for key in self.get_attrs_keys()
                    if self.source_attrs[key] != self.dest_attrs[key]
                },
                "+": {
                    key: self.source_attrs[key]
                    for key in self.get_attrs_keys()
                    if self.source_attrs[key] != self.dest_attrs[key]
                },
            }
        if self.source_attrs is None and self.dest_attrs is not None:
            return {"-": {key: self.dest_attrs[key] for key in self.get_attrs_keys()}}
        if self.source_attrs is not None and self.dest_attrs is None:
            return {"+": {key: self.source_attrs[key] for key in self.get_attrs_keys()}}
        return {}

    def add_child(self, element: "DiffElement"):
        """Attach a child object of type DiffElement.

        Childs are saved in a Diff object and are organized by type and name.

        Args:
          element: DiffElement
        """
        self.child_diff.add(element)

    def get_children(self) -> Iterator["DiffElement"]:
        """Iterate over all child DiffElements of this one."""
        yield from self.child_diff.get_children()

    def has_diffs(self, include_children: bool = True) -> bool:
        """Check whether this element (or optionally any of its children) has some diffs.

        Args:
          include_children: If True, recursively check children for diffs as well.
        """
        if (self.source_attrs is not None and self.dest_attrs is None) or (
            self.source_attrs is None and self.dest_attrs is not None
        ):
            return True
        if self.source_attrs is not None and self.dest_attrs is not None:
            for attr_key in self.get_attrs_keys():
                if self.source_attrs.get(attr_key) != self.dest_attrs.get(attr_key):
                    return True

        if include_children:
            if self.child_diff.has_diffs():
                return True

        return False

    def summary(self) -> Mapping[Text, int]:
        """Build a summary of this DiffElement and its children."""
        summary = {
            DiffSyncActions.CREATE: 0,
            DiffSyncActions.UPDATE: 0,
            DiffSyncActions.DELETE: 0,
            "no-change": 0,
        }
        if self.action:
            summary[self.action] += 1
        else:
            summary["no-change"] += 1
        child_summary = self.child_diff.summary()
        for key in summary:
            summary[key] += child_summary[key]
        return summary

    def str(self, indent: int = 0):
        """Build a detailed string representation of this DiffElement and its children."""
        margin = " " * indent
        result = f"{margin}{self.type}: {self.name}"
        if self.source_attrs is not None and self.dest_attrs is not None:
            # Only print attrs that have meaning in both source and dest
            attrs_diffs = self.get_attrs_diffs()
            for attr in attrs_diffs["+"]:
                result += (
                    f"\n{margin}  {attr}"
                    f"    {self.source_name}({attrs_diffs['+'][attr]})"
                    f"    {self.dest_name}({attrs_diffs['-'][attr]})"
                )
        elif self.dest_attrs is not None:
            result += f" MISSING in {self.source_name}"
        elif self.source_attrs is not None:
            result += f" MISSING in {self.dest_name}"

        if self.child_diff.has_diffs():
            result += "\n" + self.child_diff.str(indent + 2)
        elif self.source_attrs is None and self.dest_attrs is None:
            result += " (no diffs)"
        return result

    def dict(self) -> Mapping[Text, Mapping[Text, Any]]:
        """Build a dictionary representation of this DiffElement and its children."""
        attrs_diffs = self.get_attrs_diffs()
        result = {}
        if "-" in attrs_diffs:
            result["-"] = attrs_diffs["-"]
        if "+" in attrs_diffs:
            result["+"] = attrs_diffs["+"]
        if self.child_diff.has_diffs():
            result.update(self.child_diff.dict())
        return result
