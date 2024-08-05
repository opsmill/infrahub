from typing import Any, Optional

import requests


def get_value(obj, name: str):
    """Query a value in dot notation recursively"""
    if "." not in name:
        return obj.get(name)

    first_name, remaining_part = name.split(".", maxsplit=1)
    sub_obj = obj.get(first_name)
    if not sub_obj:
        return None
    return get_value(sub_obj, name=remaining_part)


class RestApiClient:
    def __init__(
            self,
            base_url: str,
            auth_method: str,
            api_token: Optional[str] = None,
            username: Optional[str] = None,
            password: Optional[str] = None,
            timeout: Optional[int] = 30
        ):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Determine authentication method
        if auth_method == "token" and api_token:
            self.headers["Authorization"] = f"Bearer {api_token}"
        elif auth_method == "basic" and username and password:
            self.auth = (username, password)
        else:
            raise ValueError("Invalid authentication configuration!")

        self.timeout = timeout

    def request(self, method: str, endpoint: str, params: Optional[dict[str, Any]] = None, data: Optional[dict[str, Any]] = None) -> Any:
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
                    timeout=self.timeout
                )
            else:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=data,
                    timeout=self.timeout
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

    def put(self, endpoint: str, data: Optional[dict[str, Any]] = None) -> Any:
        return self.request("PUT", endpoint, data=data)

    def delete(self, endpoint: str) -> Any:
        return self.request("DELETE", endpoint)
