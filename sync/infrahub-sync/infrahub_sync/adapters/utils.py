import operator
import re
from typing import Any, List, Optional, Union

import requests
from asteval import Interpreter
from netutils.ip import is_ip_within as netutils_is_ip_within


def is_ip_within_filter(ip: str, ip_compare: Union[str, List[str]]) -> bool:
    """Check if an IP address is within a given subnet."""
    return netutils_is_ip_within(ip=ip, ip_compare=ip_compare)


def convert_to_int(value: Any) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        raise ValueError(f"Cannot convert '{value}' to int")


def regex_filter(field_value: str, pattern: str) -> bool:
    return bool(re.match(pattern, field_value))


# Operations mapping
OPERATIONS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": lambda x, y: operator.gt(convert_to_int(x), convert_to_int(y)),
    "<": lambda x, y: operator.lt(convert_to_int(x), convert_to_int(y)),
    ">=": lambda x, y: operator.ge(convert_to_int(x), convert_to_int(y)),
    "<=": lambda x, y: operator.le(convert_to_int(x), convert_to_int(y)),
    "in": lambda x, y: y and x in y,
    "not in": lambda x, y: x not in y,
    "contains": lambda x, y: x and y in x,
    "not contains": lambda x, y: x and y not in x,
    "regex": lambda x, pattern: re.match(pattern, x) is not None,
    "is_empty": lambda x: x is None or not x,
    "is_not_empty": lambda x: x is not None and x,
    "is_ip_within": is_ip_within_filter,
}

STRING_METHODS = {
    "upper": str.upper,
    "lower": str.lower,
    "capitalize": str.capitalize,
    "title": str.title,
    "replace": str.replace,
    "join": str.join,
    "strip": str.strip,
    "lstrip": str.lstrip,
    "rstrip": str.rstrip,
    "format": str.format,
}


def apply_filter(field_value: Any, operation: str, value: Any) -> bool:
    """Apply a specified operation to a field value."""
    operation_func = OPERATIONS.get(operation)
    if operation_func is None:
        raise ValueError(f"Unsupported operation: {operation}")

    # Handle is_empty and is_not_empty which do not use the value argument
    if operation in {"is_empty", "is_not_empty"}:
        return operation_func(field_value)

    return operation_func(field_value, value)


def apply_filters(item: dict[str, Any], filters: List[dict[str, Any]]) -> bool:
    """Apply filters to an item and return True if it passes all filters."""
    for filter_obj in filters:
        field_value = get_value(obj=item, name=filter_obj["field"])
        if not apply_filter(field_value, filter_obj["operation"], filter_obj["value"]):
            return False
    return True


def apply_transform(item: dict[str, Any], transform_expr: str, field: str) -> None:
    """Apply a transformation expression to a specified field in the item."""
    try:
        # Initialize asteval interpreter
        aeval = Interpreter()
        aeval.symtable.update(STRING_METHODS)
        context = {k: v for k, v in item.items() if isinstance(v, (str, int, float, dict, list))}
        aeval.symtable.update(context)

        # Safely evaluate the expression using asteval
        transformed_value = aeval.eval(expr=transform_expr)
        # If the result is a set, convert it to a string or extract the first element
        if isinstance(transformed_value, set):
            if len(transformed_value) == 1:
                transformed_value = next(iter(transformed_value))
            else:
                transformed_value = ", ".join(transformed_value)

        # Assign the result back to the item
        item[field] = transformed_value
    except Exception as e:
        raise ValueError(f"Failed to transform '{field}' with '{transform_expr}': {e}")


def apply_transforms(item: dict[str, Any], transforms: List[dict[str, str]]) -> dict[str, Any]:
    """Apply a list of structured transformations to an item."""
    for transform_obj in transforms:
        field = transform_obj["field"]
        expr = transform_obj["expression"]
        apply_transform(item, expr, field)
    return item


def get_value(obj, name: str):
    """Query a value in dot notation recursively"""
    if "." not in name:
        # Check if the object is a dictionary and use appropriate method to access the attribute.
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)

    first_name, remaining_part = name.split(".", maxsplit=1)

    # Check if the object is a dictionary and use appropriate method to access the attribute.
    if isinstance(obj, dict):
        sub_obj = obj.get(first_name)
    else:
        sub_obj = getattr(obj, first_name, None)

    if not sub_obj:
        return None
    return get_value(obj=sub_obj, name=remaining_part)


def derive_identifier_key(obj: dict[str, Any]) -> Optional[str]:
    """Try to get obj.id, and if it doesn't exist, try to get a key ending with _id"""
    obj_id = str(obj.get("id", None))

    if not obj_id:
        for key, value in obj.items():
            if key.endswith("_id"):
                obj_id = value

    # If we still didn't find any id, raise ValueError
    if not obj_id:
        raise ValueError("No suitable identifier key found in object")
    return obj_id


class RestApiClient:
    def __init__(
        self,
        base_url: str,
        auth_method: str,
        api_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: Optional[int] = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Determine authentication method
        if auth_method == "token" and api_token:
            self.headers["Authorization"] = f"Token {api_token}"
        elif auth_method == "basic" and username and password:
            self.auth = (username, password)
        else:
            raise ValueError("Invalid authentication configuration!")

        self.timeout = timeout

    def request(
        self, method: str, endpoint: str, params: Optional[dict[str, Any]] = None, data: Optional[dict[str, Any]] = None
    ) -> Any:
        """Make a request to the REST API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            if hasattr(self, "auth"):
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=data,
                    auth=self.auth,
                    timeout=self.timeout,
                )
            else:
                response = requests.request(
                    method=method, url=url, headers=self.headers, params=params, json=data, timeout=self.timeout
                )

            response.raise_for_status()  # Raise an HTTPError for bad responses

            try:
                return response.json()
            except requests.exceptions.JSONDecodeError:
                print("Response content is not valid JSON:", response.text)  # Print the response content
                raise ValueError("Response content is not valid JSON.")

        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")

    def get(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> Any:
        return self.request("GET", endpoint, params=params)

    def post(self, endpoint: str, data: Optional[dict[str, Any]] = None) -> Any:
        return self.request("POST", endpoint, data=data)

    def patch(self, endpoint: str, data: Optional[dict[str, Any]] = None) -> Any:
        return self.request("PATCH", endpoint, data=data)

    def put(self, endpoint: str, data: Optional[dict[str, Any]] = None) -> Any:
        return self.request("PUT", endpoint, data=data)

    def delete(self, endpoint: str) -> Any:
        return self.request("DELETE", endpoint)
