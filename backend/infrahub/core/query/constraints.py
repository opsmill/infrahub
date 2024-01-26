from __future__ import annotations

from typing import TYPE_CHECKING, List

from infrahub.core.query import Query

if TYPE_CHECKING:
    from infrahub.core.schema import NodeSchema
    from infrahub.database import InfrahubDatabase


class NodeConstraintsUniquenessQuery(Query):
    name = "node_constraints_uniqueness"

    def __init__(self, schema: NodeSchema, constraints: List[str], *args, **kwargs):
        self.schema = schema
        self.filters = constraints

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        self.order_by = []

        # Add the Branch filters
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        self.params.update({"node_kind": self.schema.kind, "attr_names": [attr_schema.name for attr_schema in self.schema.unique_attributes]})
        from_times = db.render_list_comprehension(items="relationships(sub_path)", item_name="from")

        query = """
        MATCH sub_path = (sub_n:Node)-[:HAS_ATTRIBUTE]-(sub_attr:Attribute)-[:HAS_VALUE]-(sub_attr_value:AttributeValue)
        WHERE $node_kind IN LABELS(sub_n) AND (sub_attr.name IN $attr_names)
        CALL {
        WITH sub_n, sub_path, sub_attr, sub_attr_value
        WHERE all(
            r IN relationships(sub_path) WHERE (
                (
                    (%(branch_filter)s)
                        // (r.branch IN ['main', '-global-'] AND r.from <= "2024-01-26T02:10:19.000000Z" AND r.to IS NULL)
                        // OR (r.branch IN ['main', '-global-'] AND r.from <= "2024-01-26T02:10:19.000000Z" AND r.to >= "2024-01-26T02:10:19.000000Z")
                    AND r.status = "active"
                )
            )
        )
        WITH
            sub_attr,
            sub_attr_value,
            sub_path,
            reduce(br_lvl = 0, r in relationships(sub_path) | br_lvl + r.branch_level) AS branch_level
            , %(from_times)s AS from_times
        RETURN sub_n AS n, sub_attr AS attr, sub_attr_value AS attr_value
        ORDER BY
            branch_level DESC
            , from_times[1] DESC
            , from_times[2] DESC
        LIMIT 1
        }
        WITH n.kind as kind, collect(n.uuid) as node_ids, count(*) as cnt, attr.name as attr_name, attr_value.value as attr_value
        WHERE cnt > 1
        """ % {"branch_filter": branch_filter, "from_times": from_times}


        self.add_to_query(query)

        self.return_labels = ["kind", "node_ids", "cnt", "attr_name", "attr_value"]

        #         """
        #         CALL {
        #   MATCH (n:InfraDevice)
        #   MATCH (n)-[:HAS_ATTRIBUTE]-(:Attribute {name: "name"})-[:HAS_VALUE]-(av1:AttributeValue)
        #   MATCH (n)-[:IS_RELATED]-(:Relationship)-[:IS_RELATED]-(av2:BuiltinLocation)
        #   RETURN count(n) as cnt1, av1.value as value1, av2.uuid as value2
        # }
        # WITH cnt1, value1, value2
        # WHERE cnt1 > 1
        # RETURN cnt1, value1, value2
        #     
        #     """

        ###############################
        # DAMIEN'S QUERY
        ###############################
        # froms_var = db.render_list_comprehension(items="relationships(path1)", item_name="from")
        # with_clause = (
        #     "av1, av2, path1, path2,"
        #     " reduce(br_lvl = 0, r in relationships(path1) | br_lvl + r.branch_level) AS branch_level,"
        #     f" {froms_var} AS froms"
        # )
        # query = """
        # MATCH (n:Node)
        # WHERE $node_kind IN LABELS(n)
        # CALL {
        #     WITH n
        #     MATCH path1 = (n)-[:HAS_ATTRIBUTE]-(:Attribute {name: "nbr_seats"})-[:HAS_VALUE]-(av1:AttributeValue)
        #     MATCH path2 = (n)-[:HAS_ATTRIBUTE]-(:Attribute {name: "is_electric"})-[:HAS_VALUE]-(av2:AttributeValue)
        #     WHERE all(r IN relationships(path1) WHERE (%(branch_filter)s)) AND all(r IN relationships(path2) WHERE (%(branch_filter)s))
        #     WITH %(with_clause)s
        #     RETURN n as n1, av1 as av11, av2 as av22, path1 as path11, path2 as path22
        #     ORDER BY branch_level DESC, froms[-1] DESC, froms[-2] DESC
        #     LIMIT 1
        #     // RETURN n.uuid as node, r1.status as status1, rav1.value as value1
        # }
        # WITH n1, av11, av22, path11, path22
        # WHERE all(r IN relationships(path11) WHERE (r.status = "active")) AND all(r IN relationships(path22) WHERE (r.status = "active"))
        # CALL {
        #     WITH n1, av11, av22
        #     RETURN count(n1) as cnt1, av11.value as value1, av22.value as value2
        # }
        # WITH cnt1, value1, value2
        # RETURN cnt1, value1, value2
        # """ % {"branch_filter": branch_filter, "with_clause": with_clause}

        # CALL {
        # MATCH (n:Node)
        # WHERE $node_kind IN LABELS(n)
        # CALL {
        #     WITH n
        #     MATCH path1 = (n)-[:HAS_ATTRIBUTE]->(:Attribute {name: "nbr_seats"})-[:HAS_VALUE]->(av1:AttributeValue)
        #     MATCH path2 = (n)-[:HAS_ATTRIBUTE]->(:Attribute {name: "is_electric"})-[:HAS_VALUE]->(av2:AttributeValue)
        #     MATCH path3 = (n)-[:IS_RELATED]-(:Relationship { identifier: "fdsfsf "})-[:IS_RELATED]-(av3:Node)
        #     WHERE all(r IN relationships(path1) WHERE (((r.branch IN ['-global-', 'main'] AND r.from <= "2024-01-25T20:51:25.255661Z" AND r.to IS NULL)
        #     OR (r.branch IN ['-global-', 'main'] AND r.from <= "2024-01-25T20:51:25.255661Z" AND r.to >= "2024-01-25T20:51:25.255661Z")))) AND all(r IN relationships(path2) WHERE (((r.branch IN ['-global-', 'main'] AND r.from <= "2024-01-25T20:51:25.255661Z" AND r.to IS NULL)
        #     OR (r.branch IN ['-global-', 'main'] AND r.from <= "2024-01-25T20:51:25.255661Z" AND r.to >= "2024-01-25T20:51:25.255661Z"))))
        #     WITH av1, av2, path1, path2, reduce(br_lvl = 0, r in relationships(path1) | br_lvl + r.branch_level) AS branch_level, extract(i in relationships(path1) | i.from) AS froms
        #     RETURN n as n1, tostring(av1.value) as av11, tostring(av2.value) as av22, path1 as path11, path2 as path22
        #     ORDER BY branch_level DESC, froms[-1] DESC, froms[-2] DESC
        #     LIMIT 1
        # }
        # WITH n1, av11, av22, path11, path22
        # WHERE all(r IN relationships(path11) WHERE (r.status = "active")) AND all(r IN relationships(path22) WHERE (r.status = "active"))
        # // WHERE COUNT(n1, av11, av22) > 1
        # RETURN count(n1) as cnt1, av11 as value1, av22 as value2
        # ORDER BY cnt1 DESC
        # }
        # WITH cnt1, value1, value2
        # WHERE cnt1 > 1
        # RETURN cnt1, value1, value2

        # self.add_to_query(query)

        # self.return_labels = ["cnt1", "value1"]
