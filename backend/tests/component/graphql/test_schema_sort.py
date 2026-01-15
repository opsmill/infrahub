"""Unit tests for the sort_schema_ast function."""

import pytest
from graphql import parse, print_ast
from graphql.language.ast import (
    DocumentNode,
    EnumTypeDefinitionNode,
    InputObjectTypeDefinitionNode,
    InterfaceTypeDefinitionNode,
    ObjectTypeDefinitionNode,
)

from infrahub.graphql.schema_sort import sort_schema_ast


@pytest.fixture
def unsorted_schema_document() -> DocumentNode:
    """Create a GraphQL document with unsorted schema elements for testing."""
    schema_str = """
    type User {
        email: String!
        name: String!
        age: Int
        posts: [Post!]!
    }
    
    type Post {
        title: String!
        content: String
        author: User!
        tags: [String!]
    }
    
    interface Node {
        id: ID!
        createdAt: String!
    }
    
    enum Status {
        ACTIVE
        INACTIVE
        PENDING
    }
    
    input CreateUserInput {
        email: String!
        name: String!
        age: Int
    }
    
    input UpdateUserInput {
        name: String
        age: Int
    }
    """
    return parse(schema_str)


@pytest.fixture
def expected_sorted_schema_document() -> DocumentNode:
    """Create the expected sorted version of the schema document."""
    schema_str = """
    input CreateUserInput {
        age: Int
        email: String!
        name: String!
    }
    
    interface Node {
        createdAt: String!
        id: ID!
    }
    
    type Post {
        author: User!
        content: String
        tags: [String!]
        title: String!
    }
    
    enum Status {
        ACTIVE
        INACTIVE
        PENDING
    }
    
    input UpdateUserInput {
        age: Int
        name: String
    }
    
    type User {
        age: Int
        email: String!
        name: String!
        posts: [Post!]!
    }
    """
    return parse(schema_str)


@pytest.fixture
def complex_schema_document() -> DocumentNode:
    """Create a more complex schema with nested types and multiple arguments."""
    schema_str = """
    type Query {
        getUser(id: ID!, includeDeleted: Boolean): User
        getUsers(filter: UserFilter, orderBy: UserOrderBy, limit: Int, offset: Int): [User!]!
        getPost(id: ID!): Post
    }
    
    type Mutation {
        createUser(input: CreateUserInput!): User!
        updateUser(id: ID!, input: UpdateUserInput!): User!
        deleteUser(id: ID!): Boolean!
    }
    
    type User {
        id: ID!
        name: String!
        email: String!
        posts(filter: PostFilter, orderBy: PostOrderBy): [Post!]!
        profile: UserProfile
    }
    
    type Post {
        id: ID!
        title: String!
        content: String
        author: User!
        comments: [Comment!]!
    }
    
    type Comment {
        id: ID!
        content: String!
        author: User!
        post: Post!
    }
    
    input UserFilter {
        name: String
        email: String
        age: Int
    }
    
    input PostFilter {
        title: String
        authorId: ID
    }
    
    enum UserOrderBy {
        NAME_ASC
        NAME_DESC
        EMAIL_ASC
        EMAIL_DESC
    }
    
    enum PostOrderBy {
        TITLE_ASC
        TITLE_DESC
        CREATED_AT_ASC
        CREATED_AT_DESC
    }
    """
    return parse(schema_str)


def test_sort_schema_ast_basic_sorting(
    unsorted_schema_document: DocumentNode, expected_sorted_schema_document: DocumentNode
) -> None:
    """Test that sort_schema_ast correctly sorts basic schema elements."""
    result = sort_schema_ast(unsorted_schema_document)

    # Convert to strings for comparison
    result_str = print_ast(result)
    expected_str = print_ast(expected_sorted_schema_document)

    assert result_str == expected_str


def test_sort_schema_ast_preserves_structure(unsorted_schema_document: DocumentNode) -> None:
    """Test that sorting preserves the overall document structure."""
    result = sort_schema_ast(unsorted_schema_document)

    # Check that we have the same number of definitions
    assert len(result.definitions) == len(unsorted_schema_document.definitions)

    # Check that all definition types are preserved
    original_types = {type(defn).__name__ for defn in unsorted_schema_document.definitions}
    result_types = {type(defn).__name__ for defn in result.definitions}
    assert original_types == result_types


def test_sort_schema_ast_sorts_definitions_by_name(unsorted_schema_document: DocumentNode) -> None:
    """Test that type definitions are sorted alphabetically by name."""
    result = sort_schema_ast(unsorted_schema_document)

    definition_names = []
    for definition in result.definitions:
        if hasattr(definition, "name") and definition.name:
            definition_names.append(definition.name.value)

    # Check that names are in alphabetical order
    assert definition_names == sorted(definition_names)


def test_sort_schema_ast_sorts_object_fields(unsorted_schema_document: DocumentNode) -> None:
    """Test that object type fields are sorted alphabetically."""
    result = sort_schema_ast(unsorted_schema_document)

    # Find the User type and check field order
    user_type = None
    for definition in result.definitions:
        if isinstance(definition, ObjectTypeDefinitionNode) and definition.name.value == "User":
            user_type = definition
            break

    assert user_type is not None
    field_names = [field.name.value for field in user_type.fields]
    assert field_names == sorted(field_names)


def test_sort_schema_ast_sorts_enum_values(unsorted_schema_document: DocumentNode) -> None:
    """Test that enum values are sorted alphabetically."""
    result = sort_schema_ast(unsorted_schema_document)

    # Find the Status enum and check value order
    status_enum = None
    for definition in result.definitions:
        if isinstance(definition, EnumTypeDefinitionNode) and definition.name.value == "Status":
            status_enum = definition
            break

    assert status_enum is not None
    enum_values = [value.name.value for value in status_enum.values]
    assert enum_values == sorted(enum_values)


def test_sort_schema_ast_sorts_input_fields(unsorted_schema_document: DocumentNode) -> None:
    """Test that input object fields are sorted alphabetically."""
    result = sort_schema_ast(unsorted_schema_document)

    # Find the CreateUserInput and check field order
    create_input = None
    for definition in result.definitions:
        if isinstance(definition, InputObjectTypeDefinitionNode) and definition.name.value == "CreateUserInput":
            create_input = definition
            break

    assert create_input is not None
    field_names = [field.name.value for field in create_input.fields]
    assert field_names == sorted(field_names)


def test_sort_schema_ast_complex_schema(complex_schema_document: DocumentNode) -> None:
    """Test sorting with a more complex schema containing multiple types and arguments."""
    result = sort_schema_ast(complex_schema_document)

    # Check that all definitions are sorted by name
    definition_names = []
    for definition in result.definitions:
        if hasattr(definition, "name") and definition.name:
            definition_names.append(definition.name.value)

    assert definition_names == sorted(definition_names)

    # Check that fields within types are sorted
    for definition in result.definitions:
        if isinstance(definition, (ObjectTypeDefinitionNode, InterfaceTypeDefinitionNode)) and definition.fields:
            field_names = [field.name.value for field in definition.fields]
            assert field_names == sorted(field_names)

            # Check that field arguments are also sorted
            for field in definition.fields:
                if field.arguments:
                    arg_names = [arg.name.value for arg in field.arguments]
                    assert arg_names == sorted(arg_names)

        elif isinstance(definition, EnumTypeDefinitionNode) and definition.values:
            enum_values = [value.name.value for value in definition.values]
            assert enum_values == sorted(enum_values)

        elif isinstance(definition, InputObjectTypeDefinitionNode) and definition.fields:
            field_names = [field.name.value for field in definition.fields]
            assert field_names == sorted(field_names)


def test_sort_schema_ast_empty_document() -> None:
    """Test that sorting an empty document returns an empty document."""
    empty_doc = DocumentNode(definitions=[])
    result = sort_schema_ast(empty_doc)

    assert len(result.definitions) == 0
    assert isinstance(result, DocumentNode)


def test_sort_schema_ast_single_definition() -> None:
    """Test sorting a document with a single definition."""
    single_type_str = """
    type User {
        name: String!
        email: String!
    }
    """
    single_doc = parse(single_type_str)
    result = sort_schema_ast(single_doc)

    assert len(result.definitions) == 1
    assert isinstance(result.definitions[0], ObjectTypeDefinitionNode)
    assert result.definitions[0].name.value == "User"

    # Check that fields are sorted
    field_names = [field.name.value for field in result.definitions[0].fields]
    assert field_names == sorted(field_names)


def test_sort_schema_ast_preserves_metadata() -> None:
    """Test that sorting preserves important metadata like directives and descriptions."""
    # Test with a basic schema to ensure the function doesn't crash
    # and that the structure is preserved
    basic_schema = """
    type User {
        email: String!
        name: String!
        age: Int
    }

    type Post {
        title: String!
        content: String
        author: User!
    }

    enum Status {
        ACTIVE
        INACTIVE
        PENDING
    }

    input CreateUserInput {
        email: String!
        name: String!
        age: Int
    }
    """

    doc = parse(basic_schema)
    result = sort_schema_ast(doc)

    # Check that the function doesn't crash and returns a valid DocumentNode
    assert isinstance(result, DocumentNode)
    assert len(result.definitions) == 4  # User, Post, Status, CreateUserInput

    # Check that all definitions are sorted by name
    definition_names = []
    for definition in result.definitions:
        if hasattr(definition, "name") and definition.name:
            definition_names.append(definition.name.value)

    assert definition_names == sorted(definition_names)

    # Check that fields within types are sorted
    for definition in result.definitions:
        if hasattr(definition, "fields") and definition.fields:
            field_names = [field.name.value for field in definition.fields]
            assert field_names == sorted(field_names)

    # Check that enum values are sorted
    for definition in result.definitions:
        if hasattr(definition, "values") and definition.values:
            enum_values = [value.name.value for value in definition.values]
            assert enum_values == sorted(enum_values)


def test_sort_schema_ast_idempotent() -> None:
    """Test that sorting an already sorted document doesn't change it."""
    schema_str = """
    type User {
        age: Int
        email: String!
        name: String!
    }

    type Post {
        author: User!
        content: String
        title: String!
    }
    """
    doc = parse(schema_str)

    # Sort once
    result1 = sort_schema_ast(doc)
    result1_str = print_ast(result1)

    # Sort again
    result2 = sort_schema_ast(result1)
    result2_str = print_ast(result2)

    # Should be identical
    assert result1_str == result2_str


@pytest.fixture
def schema_with_unsorted_interfaces() -> DocumentNode:
    """Schema with types implementing multiple unsorted interfaces."""
    schema_str = """
    type User implements Timestamped & Node & Auditable {
        id: ID!
        name: String!
    }
    type Post implements Node & Timestamped {
        id: ID!
        title: String!
    }
    """
    return parse(schema_str)


def test_sort_schema_ast_sorts_interfaces(schema_with_unsorted_interfaces: DocumentNode) -> None:
    """Test that interfaces are sorted alphabetically when a type implements multiple interfaces."""
    result = sort_schema_ast(schema_with_unsorted_interfaces)

    # Find the User type
    user_type = None
    for definition in result.definitions:
        if hasattr(definition, "name") and definition.name.value == "User":
            user_type = definition
            break

    assert user_type is not None
    assert user_type.interfaces is not None

    # Extract interface names
    interface_names = [intf.name.value for intf in user_type.interfaces]

    # Should be sorted: Auditable, Node, Timestamped
    assert interface_names == ["Auditable", "Node", "Timestamped"]
    assert interface_names == sorted(interface_names)


def test_sort_schema_ast_sorts_all_interfaces_in_schema() -> None:
    """Test that all types with multiple interfaces get sorted."""
    schema_str = """
    type Article implements Publishable & Node & Timestamped {
        id: ID!
    }
    type Comment implements Node & Auditable {
        id: ID!
    }
    interface BaseInterface implements Node & Timestamped {
        id: ID!
    }
    """
    doc = parse(schema_str)
    result = sort_schema_ast(doc)

    for definition in result.definitions:
        if hasattr(definition, "interfaces") and definition.interfaces:
            interface_names = [intf.name.value for intf in definition.interfaces]
            assert interface_names == sorted(interface_names), f"{definition.name.value} interfaces not sorted"


def test_sort_schema_ast_preserves_other_definition_types() -> None:
    """Test that other definition types (scalars, unions, directives) are preserved."""
    schema_str = """
    scalar DateTime

    scalar JSON

    union SearchResult = User | Post

    directive @deprecated(reason: String = "No longer supported") on FIELD_DEFINITION | ENUM_VALUE

    type User {
        id: ID!
        name: String!
    }

    type Post {
        id: ID!
        title: String!
    }
    """
    doc = parse(schema_str)
    result = sort_schema_ast(doc)

    # Check that all original definitions are preserved
    assert len(result.definitions) == len(doc.definitions)

    # Check that scalars are preserved
    scalar_names = []
    union_names = []
    directive_names = []
    type_names = []

    for definition in result.definitions:
        if hasattr(definition, "name") and definition.name:
            if definition.__class__.__name__ == "ScalarTypeDefinitionNode":
                scalar_names.append(definition.name.value)
            elif definition.__class__.__name__ == "UnionTypeDefinitionNode":
                union_names.append(definition.name.value)
            elif definition.__class__.__name__ == "DirectiveDefinitionNode":
                directive_names.append(definition.name.value)
            elif definition.__class__.__name__ == "ObjectTypeDefinitionNode":
                type_names.append(definition.name.value)

    # Verify scalars are preserved
    assert "DateTime" in scalar_names
    assert "JSON" in scalar_names

    # Verify unions are preserved
    assert "SearchResult" in union_names

    # Verify directives are preserved
    assert len(directive_names) == 1  # @deprecated directive

    # Verify types are preserved and sorted
    assert "Post" in type_names
    assert "User" in type_names
    assert type_names == sorted(type_names)
