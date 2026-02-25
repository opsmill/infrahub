from io import BytesIO

import pytest
from graphql import GraphQLError
from graphql.language import ast
from starlette.datastructures import UploadFile

from infrahub.graphql.types import Upload


def test_upload_serialize_raises_error() -> None:
    """Test that serializing Upload raises an error since it's input-only."""
    with pytest.raises(GraphQLError, match="Upload scalar cannot be serialized"):
        Upload.serialize("any value")


def test_upload_parse_literal_raises_error() -> None:
    """Test that parse_literal raises an error since uploads must use multipart."""
    node = ast.StringValueNode(value="test")

    with pytest.raises(GraphQLError, match="Upload scalar cannot be used as a literal value"):
        Upload.parse_literal(node)


def test_upload_parse_value_returns_file() -> None:
    """Test that parse_value returns the file object as-is."""
    upload_file = UploadFile(file=BytesIO(b"test content"), filename="test.txt")
    result = Upload.parse_value(value=upload_file)

    assert result is upload_file


def test_upload_parse_value_returns_none() -> None:
    """Test that parse_value returns None when no file is provided."""
    result = Upload.parse_value(value=None)

    assert result is None
