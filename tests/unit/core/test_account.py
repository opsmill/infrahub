from infrahub.core import registry
from infrahub.core.account import validate_token
from infrahub.core.node import Node


def test_validate_user_create(default_branch, register_core_models_schema):

    account_schema = registry.get_schema("Account")
    account_token_schema = registry.get_schema("AccountToken")

    user1 = Node(account_schema).new(name="user1").save()
    Node(account_token_schema).new(token="123456789", account=user1).save()


def test_validate_token(default_branch, register_core_models_schema):

    account_schema = registry.get_schema("Account")
    account_token_schema = registry.get_schema("AccountToken")

    user1 = Node(account_schema).new(name="user1").save()
    Node(account_token_schema).new(token="123456789", account=user1).save()

    assert validate_token("123456789") == "user1"
    assert validate_token("987654321") is False
