from __future__ import annotations

from infrahub.core import get_branch
from infrahub.core.query import Query


class AccountTokenValidateQuery(Query):
    def __init__(self, token, *args, **kwargs):

        self.token = token
        super().__init__(*args, **kwargs)

    def query_init(self):

        token_filter_perms, token_params = self.branch.get_query_filter_relationships(
            rel_labels=["r1", "r2"], at=self.at, include_outside_parentheses=True
        )
        self.params.update(token_params)

        account_filter_perms, account_params = self.branch.get_query_filter_relationships(
            rel_labels=["r3", "r4", "r5", "r6"], at=self.at, include_outside_parentheses=True
        )
        self.params.update(account_params)

        self.params["token_value"] = self.token

        query = """
        MATCH (at:AccountToken)-[r1:HAS_ATTRIBUTE]-(a:Attribute {name: "token"})-[r2:HAS_VALUE]-(av:AttributeValue { value: $token_value })
        WHERE %s
        WITH at
        MATCH (at)-[r3]-(:Relationship)-[r4]-(acc:Account)-[r5:HAS_ATTRIBUTE]-(a:Attribute {name: "name"})-[r6:HAS_VALUE]-(av:AttributeValue)
        WHERE %s
        """ % (
            "\n AND ".join(token_filter_perms),
            "\n AND ".join(account_filter_perms),
        )

        self.add_to_query(query)

        self.return_labels = ["at", "av"]

    def get_account_name(self):
        """Return the account name that matched the query or None."""
        if result := self.get_result():
            return result.get("av").get("value")

        return None


def validate_token(token, branch=None, at=None):

    branch = get_branch(branch)
    query = AccountTokenValidateQuery(branch=branch, token=token, at=at).execute()
    account_name = query.get_account_name()

    return account_name or False
