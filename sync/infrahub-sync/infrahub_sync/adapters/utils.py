from typing import Any, Optional

import requests


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
    obj_id = obj.get("id", None)
    if obj_id is None:
        for key, value in obj.items():
            if key.endswith("_id"):
                if value:
                    obj_id = value
                    break

    # If we still didn't find any id, raise ValueError
    if obj_id is None:
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
        # -> Peering Manager
        if auth_method == "token" and api_token:
            self.headers["Authorization"] = f"Token {api_token}"
        # -> LibreNMS
        elif auth_method == "x-auth-token" and api_token:
            self.headers["X-Auth-Token"] = api_token
        # -> Peering DB
        elif auth_method == "api-key" and api_token:
            self.headers["Authorization"] = f"Api-Key {api_token}"
        # -> RIPE API
        elif auth_method == "key" and api_token:
            self.headers["Authorization"] = f"Key {api_token}"
        # -> Observium
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
            except requests.exceptions.JSONDecodeError as exc:
                print("Response content is not valid JSON:", response.text)  # Print the response content
                raise ValueError("Response content is not valid JSON.") from exc

        except requests.exceptions.RequestException as exc:
            raise ConnectionError(f"API request failed: {str(exc)}") from exc

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
