import asyncio
import logging
from typing import List, Optional

import httpx


class ServerNotReacheableError(Exception):
    def __init__(self, address, message=None):
        self.address = address
        self.message = message or f"Unable to connect to '{address}'."
        super().__init__(self.message)


class ServerNotResponsiveError(Exception):
    def __init__(self, url, message=None):
        self.url = url
        self.message = message or f"Unable to read from '{url}'."
        super().__init__(self.message)


class GraphQLError(Exception):
    def __init__(self, errors: List[str], query: str = None, variables: dict = None):
        self.query = query
        self.variables = variables
        self.errors = errors
        self.message = f"An error occured while executing the GraphQL Query {self.query}, {self.errors}"
        super().__init__(self.message)


class NetboxClient:
    def __init__(
        self,
        address: str,
        token: str,
        retry_on_failure: bool = True,
        log: Optional[logging.Logger] = None,
        retry_delay: int = 5,
        default_timeout: int = 10,
    ):
        self.token = token
        self.address = address
        self.retry_on_failure = retry_on_failure

        self.default_timeout = default_timeout

        self.retry_delay = retry_delay
        self.log = log or logging.getLogger("netbox_client")

        self.headers = {"Content-Type": "application/json", "Authorization": f"Token {self.token}"}

    @classmethod
    async def init(cls, *args, **kwargs):
        return cls(*args, **kwargs)

    async def execute_graphql(  # pylint: disable=too-many-branches
        self,
        query: str,
        variables: dict = None,
        timeout: int = None,
        raise_for_error: bool = True,
    ):
        """Execute a GraphQL query (or mutation).
        If retry_on_failure is True, the query will retry until the server becomes reacheable.

        Args:
            query (_type_): GraphQL Query to execute, can be a query or a mutation
            variables (dict, optional): Variables to pass along with the GraphQL query. Defaults to None.
            timeout (int, optional): Timeout in second for the query. Defaults to None.
            raise_for_error (bool, optional): Flag to indicate that we need to raise an exception if the response has some errors. Defaults to True.

        Raises:
            GraphQLError: _description_

        Returns:
            _type_: _description_
        """
        url = f"{self.address}/graphql/"

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        retry = True
        while retry:
            retry = self.retry_on_failure
            try:
                resp = await self.post(url=url, payload=payload, timeout=timeout)

                if raise_for_error:
                    resp.raise_for_status()

                retry = False
            except ServerNotReacheableError:
                if retry:
                    self.log.warning(
                        f"Unable to connect to {self.address}, will retry in {self.retry_delay} seconds .."
                    )
                    await asyncio.sleep(delay=self.retry_delay)
                else:
                    self.log.error(f"Unable to connect to {self.address} .. ")
                    raise

        response = resp.json()

        if "errors" in response:
            raise GraphQLError(errors=response["errors"], query=query, variables=variables)

        return response["data"]

    async def post(self, url: str, payload: dict, timeout: int = None):
        """Execute a HTTP POST with HTTPX.

        Raises:
            ServerNotReacheableError if we are not able to connect to the server
        """
        async with httpx.AsyncClient() as client:
            try:
                return await client.post(
                    url=url,
                    json=payload,
                    headers=self.headers,
                    timeout=timeout or self.default_timeout,
                )
            except httpx.ConnectError as exc:
                raise ServerNotReacheableError(address=self.address) from exc
            except httpx.ReadTimeout as exc:
                raise ServerNotResponsiveError(url=url) from exc
