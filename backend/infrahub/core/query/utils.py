from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Tuple, Union

from neo4j import AsyncSession

from infrahub.core.query import QueryNode, QueryRel

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import AttributeSchema, RelationshipSchema


async def build_subquery_filter(
    session: AsyncSession,
    field: Union[AttributeSchema, RelationshipSchema],
    filter_name: str,
    filter_value: Any,
    branch_filter: str,
    name: Optional[str] = None,
    branch: Branch = None,
    subquery_idx: Optional[str] = 1,
) -> Tuple[str, dict[str, Any], str]:
    params = {}
    prefix = f"filter{subquery_idx}"

    field_filter, field_params, field_where = await field.get_query_filter(
        session=session,
        name=name,
        include_match=True,
        filter_name=filter_name,
        filter_value=filter_value,
        branch=branch,
        param_prefix=prefix,
    )
    params.update(field_params)

    # Assign new names to all of the relationships to ensure they are not conflicting with anything
    # The relationship will be used to generate the ordering of the results
    nbr_relationships = 0
    rel_names = []
    for item in field_filter:
        if not isinstance(item, QueryRel):
            continue
        nbr_relationships += 1
        rel_name = f"f{subquery_idx}r{nbr_relationships}"
        item.name = rel_name
        rel_names.append(rel_name)

    field_where.append("all(r IN relationships(p) WHERE (%s))" % branch_filter)
    filter_str = "-".join([str(item) for item in field_filter])
    where_str = " AND ".join(field_where)
    order_str = "[ " + ", ".join([f"{rel}.from" for rel in rel_names]) + " ]"

    query = f"""
    WITH n
    MATCH p = {filter_str}
    WHERE {where_str}
    RETURN n as {prefix}
    ORDER BY {order_str}
    LIMIT 1
    """

    return query, params, prefix


async def build_subquery_order(
    session: AsyncSession,
    field: Union[AttributeSchema, RelationshipSchema],
    order_by: str,
    branch_filter: str,
    name: Optional[str] = None,
    branch: Branch = None,
    subquery_idx: Optional[str] = 1,
) -> Tuple[str, dict[str, Any], str]:
    params = {}
    prefix = f"order{subquery_idx}"

    field_filter, field_params, field_where = await field.get_query_filter(
        session=session,
        name=name,
        include_match=False,
        filter_name=order_by,
        filter_value=None,
        branch=branch,
        param_prefix=prefix,
    )
    params.update(field_params)

    # Assign new names to all of the relationships to ensure they are not conflicting with anything
    # The relationship will be used to generate the ordering of the results
    # Just in case, clear the name on all the nodes except the last one that will be called last
    nbr_relationships = 0
    rel_names = []
    for item in field_filter:
        if isinstance(item, QueryRel):
            nbr_relationships += 1
            rel_name = f"ord{subquery_idx}r{nbr_relationships}"
            item.name = rel_name
            rel_names.append(rel_name)
        elif isinstance(item, QueryNode):
            item.name = None

    if not isinstance(field_filter[-1], QueryNode):
        raise IndexError(f"The last item in field_filter must be a QueryNode not {type(field_filter[-1])}")

    field_filter[-1].name = "last"

    field_where.append("all(r IN relationships(p) WHERE (%s))" % branch_filter)
    filter_str = "(n)-" + "-".join([str(item) for item in field_filter])
    where_str = " AND ".join(field_where)
    order_str = "[ " + ", ".join([f"{rel}.from" for rel in rel_names]) + " ]"

    query = f"""
    WITH n
    MATCH p = {filter_str}
    WHERE {where_str}
    RETURN last.value as {prefix}
    ORDER BY {order_str}
    LIMIT 1
    """

    return query, params, prefix
