from graphene import InputObjectType, String


class ContextAccountInput(InputObjectType):
    id = String(required=True, description="The Infrahub ID of the account")


class ContextInput(InputObjectType):
    account = ContextAccountInput(
        required=False,
        description="The account context can be used to override the account information that will be associated with the mutation",
    )
