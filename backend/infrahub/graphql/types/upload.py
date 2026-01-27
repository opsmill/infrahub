from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Scalar
from graphql import GraphQLError

if TYPE_CHECKING:
    from graphql.language import ast
    from starlette.datastructures import UploadFile


class Upload(Scalar):
    """GraphQL scalar for file uploads.

    This scalar type handles file uploads in `multipart/form-data requests` following the GraphQL Multipart Request specification.

    The `Upload` scalar is input-only and cannot be used in query responses.
    """

    @staticmethod
    def serialize(_value: object) -> None:
        """Serialize is not supported for `Upload` scalar.

        Upload is an input-only type and cannot be returned in query responses.
        """
        raise GraphQLError("Upload scalar cannot be serialized. It is input-only.")

    @staticmethod
    def parse_value(value: UploadFile | None) -> UploadFile | None:
        """Parse the value from multipart form data.

        Args:
            value: A `UploadFile` object from Starlette's multipart parsing, or `None` if no file was provided.

        Returns:
            A Starlette's `UploadFile` object, or `None` if no file was provided.
        """
        return value

    @staticmethod
    def parse_literal(_node: ast.Node, _variables: dict[str, Any] | None = None) -> None:
        """Parse literal values is not supported for `Upload` scalar.

        `Upload` values must be provided via multipart form data, not as literal values in the GraphQL query.
        """
        raise GraphQLError("Upload scalar cannot be used as a literal value. Use multipart form data.")
