import glob
import hashlib
import json
import os
from itertools import groupby
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

import httpx
import yaml
from git.repo import Repo
from graphql import (  # pylint: disable=no-name-in-module
    FieldNode,
    InlineFragmentNode,
    SelectionSetNode,
)

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]


class YamlFile(pydantic.BaseModel):
    identifier: str
    location: Path
    content: Optional[dict] = None
    valid: bool = True
    error_message: Optional[str] = None

    def load_content(self) -> None:
        try:
            self.content = yaml.safe_load(self.location.read_text())
        except yaml.YAMLError:
            self.error_message = "Invalid YAML/JSON file"
            self.valid = False


def base36encode(number: int) -> str:
    if not isinstance(number, (int)):
        raise TypeError("number must be an integer")
    is_negative = number < 0
    number = abs(number)

    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    base36 = ""

    while number:
        number, i = divmod(number, 36)
        base36 = alphabet[i] + base36
    if is_negative:
        base36 = "-" + base36

    return base36 or alphabet[0]


def base36decode(data: str) -> int:
    return int(data, 36)


def base16decode(data: str) -> int:
    return int(data, 16)


def base16encode(number: int) -> str:
    if not isinstance(number, (int)):
        raise TypeError("number must be an integer")
    is_negative = number < 0
    number = abs(number)

    alphabet = "0123456789abcdef"
    base16 = ""

    while number:
        number, i = divmod(number, 16)
        base16 = alphabet[i] + base16
    if is_negative:
        base16 = "-" + base16

    return base16 or alphabet[0]


def get_fixtures_dir() -> Path:
    """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
    here = os.path.abspath(os.path.dirname(__file__))
    fixtures_dir = os.path.join(here, "..", "tests", "fixtures")

    return Path(os.path.abspath(fixtures_dir))


def is_valid_uuid(value: Any) -> bool:
    """Check if the input is a valid UUID."""
    try:
        UUID(str(value))
        return True
    except ValueError:
        return False


def generate_uuid() -> str:
    return str(uuid4())


def duplicates(input_list: list) -> list:
    """Identify and return all the duplicates in a list."""

    dups = []

    clean_input_list = [item for item in input_list or [] if item is not None]
    for x, y in groupby(sorted(clean_input_list)):
        #  list(y) returns all the occurences of item x
        if len(list(y)) > 1:
            dups.append(x)

    return dups


def intersection(list1: List[Any], list2: List[Any]) -> list:
    """Calculate the intersection between 2 lists."""
    return list(set(list1) & set(list2))


def compare_lists(list1: List[Any], list2: List[Any]) -> Tuple[List[Any], List[Any], List[Any]]:
    """Compare 2 lists and return :
    - the intersection of both
    - the item present only in list1
    - the item present only in list2
    """

    in_both = intersection(list1=list1, list2=list2)
    in_list_1 = list(set(list1) - set(in_both))
    in_list_2 = list(set(list2) - set(in_both))

    return sorted(in_both), sorted(in_list_1), sorted(in_list_2)


def deep_merge_dict(dicta: dict, dictb: dict, path: Optional[List] = None) -> dict:
    """Deep Merge dictionnary B into Dictionnary A.
    Code is inspired by https://stackoverflow.com/a/7205107
    """
    if path is None:
        path = []
    for key in dictb:
        if key in dicta:
            if isinstance(dicta[key], dict) and isinstance(dictb[key], dict):
                deep_merge_dict(dicta[key], dictb[key], path + [str(key)])
            elif dicta[key] == dictb[key]:
                pass
            else:
                raise ValueError("Conflict at %s" % ".".join(path + [str(key)]))
        else:
            dicta[key] = dictb[key]
    return dicta


def str_to_bool(value: str) -> bool:
    """Convert a String to a Boolean"""

    if isinstance(value, bool):
        return value

    if isinstance(value, int) and value in [0, 1]:
        return bool(value)

    if not isinstance(value, str):
        raise TypeError(f"{value} must be a string")

    MAP = {
        "y": True,
        "yes": True,
        "t": True,
        "true": True,
        "on": True,
        "1": True,
        "n": False,
        "no": False,
        "f": False,
        "false": False,
        "off": False,
        "0": False,
    }
    try:
        return MAP[value.lower()]
    except KeyError as exc:
        raise ValueError(f"{value} can not be converted into a boolean") from exc


def get_flat_value(obj: Any, key: str, separator: str = "__") -> Any:
    """Query recursively an value defined in a flat notation (string), on a hierarchy of objects

    Examples:
        name__value
        module.object.value
    """
    if separator not in key:
        return getattr(obj, key)

    first_part, remaining_part = key.split(separator, maxsplit=1)
    sub_obj = getattr(obj, first_part)
    if not sub_obj:
        return None
    return get_flat_value(obj=sub_obj, key=remaining_part, separator=separator)


def generate_request_filename(request: httpx.Request) -> str:
    """Return a filename for a request sent to the Infrahub API

    This function is used when recording and playing back requests, as Infrahub is using a GraphQL
    API it's not possible to rely on the URL endpoint alone to separate one request from another,
    for this reason a hash of the payload is included in a filename.
    """
    formatted = (
        str(request.url).replace(":", "_").replace("//", "").replace("/", "__").replace("?", "_q_").replace("&", "_a_")
    )
    filename = f"{request.method}_{formatted}"
    if request.content:
        content_hash = hashlib.sha224(request.content)
        filename += f"_{content_hash.hexdigest()}"

    return filename.lower()


def is_valid_url(url: str) -> bool:
    try:
        parsed = httpx.URL(url)
        return all([parsed.scheme, parsed.netloc])
    except TypeError:
        return False


def find_files(
    extension: Union[str, List[str]],
    directory: Union[str, Path] = ".",
    recursive: bool = True,
) -> List[Path]:
    files = []

    if isinstance(extension, str):
        extension = [extension]

    for ext in extension:
        files.extend(glob.glob(f"{directory}/**/*.{ext}", recursive=recursive))
        files.extend(glob.glob(f"{directory}/**/.*.{ext}", recursive=recursive))

    return [Path(item) for item in files]


def get_branch(branch: Optional[str] = None, directory: Union[str, Path] = ".") -> str:
    """If branch isn't provide, return the name of the local Git branch."""
    if branch:
        return branch

    repo = Repo(directory)
    return str(repo.active_branch)


def dict_hash(dictionary: Dict[str, Any]) -> str:
    """MD5 hash of a dictionary."""
    # We need to sort arguments so {'a': 1, 'b': 2} is
    # the same as {'b': 2, 'a': 1}
    encoded = json.dumps(dictionary, sort_keys=True).encode()
    dhash = hashlib.md5(encoded)
    return dhash.hexdigest()


def calculate_dict_depth(data: dict, level: int = 1) -> int:
    """Calculate the depth of a nested dictionnary recursively."""
    if not isinstance(data, dict) or not data:
        return level
    return max(calculate_dict_depth(data=data[key], level=level + 1) for key in data)


def calculate_dict_height(data: dict, cnt: int = 0) -> int:
    """Calculate the number of fields (height) in a nested dictionnary recursively."""
    for key in data:
        if isinstance(data[key], dict):
            cnt = calculate_dict_height(data=data[key], cnt=cnt + 1)
        else:
            cnt += 1
    return cnt


async def extract_field(node: Union[FieldNode, InlineFragmentNode]) -> Optional[Dict[str, Dict]]:
    """Extract fields from a single node."""
    sub_selection_set = getattr(node, "selection_set", None)
    if not isinstance(sub_selection_set, SelectionSetNode):
        return None

    value = await extract_fields(sub_selection_set)
    if not isinstance(value, dict):
        return None

    return {node.name.value: value} if isinstance(node, FieldNode) else value


async def extract_fields(selection_set: SelectionSetNode) -> Optional[Dict[str, Dict]]:
    """This function extract all the requested fields in a tree of Dict from a SelectionSetNode

    The goal of this function is to limit the fields that we need to query from the backend.

    Currently the function support Fields and InlineFragments but in a combined tree where the fragments are merged together
    This implementation may seam counter intuitive but in the current implementation
    it's better to have slightly more information at time passed to the query manager.

    In the future we'll probably need to redesign how we read GraphQL queries to generate better Database query.
    """
    if not selection_set:
        return None

    fields: Dict[Any, Any] = {}
    for node in getattr(selection_set, "selections", []):
        if isinstance(node, (FieldNode, InlineFragmentNode)):
            node_value = await extract_field(node)
            if node_value:
                for key, value in node_value.items():
                    fields.setdefault(key, {}).update(value)

    return fields
