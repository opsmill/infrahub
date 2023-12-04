from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Tuple, Union

from infrahub.core.query import QueryNode, QueryRel
from infrahub.types import get_attribute_type

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import AttributeSchema, RelationshipSchema
    from infrahub.database import InfrahubDatabase


async def build_subquery_filter(
    db: InfrahubDatabase,
    filter_name: str,
    filter_value: Any,
    branch_filter: str,
    field: Optional[Union[AttributeSchema, RelationshipSchema]] = None,
    node_alias: str = "n",
    name: Optional[str] = None,
    branch: Branch = None,
    subquery_idx: int = 1,
) -> Tuple[str, dict[str, Any], str]:
    params = {}
    prefix = f"filter{subquery_idx}"

    # If the field is not provided, it means that the query is targeting a special keyword like:: any or attribute
    # Currently any and attribute have the same effect and relationship is not supported yet
    if field:
        get_query_filter = field.get_query_filter
    elif name in ["any", "attribute"]:
        default_attribute = get_attribute_type()
        base_attribute = default_attribute.get_infrahub_class()
        get_query_filter = base_attribute.get_query_filter
    else:
        raise ValueError("Either a field must be provided or name must be any or attribute")

    field_filter, field_params, field_where = await get_query_filter(
        name=name,
        include_match=False,
        filter_name=filter_name,
        filter_value=filter_value,
        branch=branch,
        param_prefix=prefix,
        db=db,
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
    filter_str = f"({node_alias})" + "".join([str(item) for item in field_filter])
    where_str = " AND ".join(field_where)
    order_str = ", ".join([f"{rel}.branch_level DESC, {rel}.from DESC" for rel in rel_names])
    query = f"""
    WITH {node_alias}
    MATCH p = {filter_str}
    WHERE {where_str}
    RETURN {node_alias} as {prefix}
    ORDER BY {order_str}
    LIMIT 1
    """

    return query, params, prefix


async def build_subquery_order(
    db: InfrahubDatabase,
    field: Union[AttributeSchema, RelationshipSchema],
    order_by: str,
    branch_filter: str,
    node_alias: str = "n",
    name: Optional[str] = None,
    branch: Branch = None,
    subquery_idx: int = 1,
) -> Tuple[str, dict[str, Any], str]:
    params = {}
    prefix = f"order{subquery_idx}"

    field_filter, field_params, field_where = await field.get_query_filter(
        db=db,
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
    filter_str = f"({node_alias})" + "".join([str(item) for item in field_filter])
    where_str = " AND ".join(field_where)
    order_str = ", ".join([f"{rel}.branch_level DESC, {rel}.from DESC" for rel in rel_names])

    query = f"""
    WITH {node_alias}
    MATCH p = {filter_str}
    WHERE {where_str}
    RETURN last.value as {prefix}
    ORDER BY {order_str}
    LIMIT 1
    """

    return query, params, prefix
