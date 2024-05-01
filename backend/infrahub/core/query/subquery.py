from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Tuple, Union

from infrahub.core.query import QueryNode

from .attribute import default_attribute_query_filter

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
    partial_match: bool = False,
    optional_match: bool = False,
    result_prefix: str = "filter",
    support_profiles: bool = False,
    extra_tail_properties: Optional[dict[str, str]] = None,
) -> Tuple[str, dict[str, Any], str]:
    support_profiles = support_profiles and field and field.is_attribute and filter_name in ("value", "values")
    params = {}
    prefix = f"{result_prefix}{subquery_idx}"

    # If the field is not provided, it means that the query is targeting a special keyword like:: any or attribute
    # Currently any and attribute have the same effect and relationship is not supported yet
    if field:
        query_filter_function = field.get_query_filter
    elif name in ["any", "attribute"]:
        query_filter_function = default_attribute_query_filter
    else:
        raise ValueError("Either a field must be provided or name must be any or attribute")

    field_filter, field_params, field_where = await query_filter_function(
        name=name,
        include_match=False,
        filter_name=filter_name,
        filter_value=filter_value,
        branch=branch,
        param_prefix=prefix,
        db=db,
        partial_match=partial_match,
        support_profiles=support_profiles,
    )
    params.update(field_params)

    field_where.append("all(r IN relationships(path) WHERE (%s))" % branch_filter)
    filter_str = f"({node_alias})" + "".join([str(item) for item in field_filter])
    where_str = " AND ".join(field_where)
    branch_level_str = "reduce(br_lvl = 0, r in relationships(path) | br_lvl + r.branch_level)"
    froms_str = db.render_list_comprehension(items="relationships(path)", item_name="from")
    to_return = f"{node_alias} as {prefix}, is_active"
    with_extra = ""
    if extra_tail_properties:
        tail_node = field_filter[-1]
        with_extra += f", {tail_node.name}"
        for variable_name, tail_property in extra_tail_properties.items():
            to_return += f", {tail_node.name}.{tail_property} as {variable_name}"
    match = "OPTIONAL MATCH" if optional_match else "MATCH"
    query = f"""
    WITH {node_alias}
    {match} path = {filter_str}
    WHERE {where_str}
    WITH
        {node_alias},
        path,
        {branch_level_str} AS branch_level,
        {froms_str} AS froms,
        all(r IN relationships(path) WHERE r.status = "active") as is_active{with_extra}
    RETURN {to_return}
    ORDER BY branch_level DESC, froms[-1] DESC, froms[-2] DESC
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
    result_prefix: Optional[str] = None,
    support_profiles: bool = False,
    extra_tail_properties: Optional[dict[str, str]] = None,
) -> Tuple[str, dict[str, Any], str]:
    support_profiles = support_profiles and field and field.is_attribute and order_by in ("value", "values")
    params = {}
    prefix = result_prefix or f"order{subquery_idx}"

    field_filter, field_params, field_where = await field.get_query_filter(
        db=db,
        name=name,
        include_match=False,
        filter_name=order_by,
        filter_value=None,
        branch=branch,
        param_prefix=prefix,
        support_profiles=support_profiles,
    )
    params.update(field_params)

    for item in field_filter:
        item.name = None

    if not isinstance(field_filter[-1], QueryNode):
        raise IndexError(f"The last item in field_filter must be a QueryNode not {type(field_filter[-1])}")

    field_filter[-1].name = "last"

    field_where.append("all(r IN relationships(path) WHERE (%s))" % branch_filter)
    filter_str = f"({node_alias})" + "".join([str(item) for item in field_filter])
    where_str = " AND ".join(field_where)
    branch_level_str = "reduce(br_lvl = 0, r in relationships(path) | br_lvl + r.branch_level)"
    froms_str = db.render_list_comprehension(items="relationships(path)", item_name="from")
    to_return = f"last.{order_by if order_by != 'values' and '__' not in order_by else 'value'} as {prefix}"
    with_parts: dict[str, Optional[str]] = {
        "last": None,
        "path": None,
        branch_level_str: "branch_level",
        froms_str: "froms",
    }
    if extra_tail_properties:
        tail_node = field_filter[-1]
        if tail_node.name not in with_parts:
            with_parts[tail_node.name] = None
        tail_node_name = with_parts.get(tail_node.name) or tail_node.name
        for variable_name, tail_property in extra_tail_properties.items():
            to_return += f", {tail_node_name}.{tail_property} as {variable_name}"
    with_str = ", ".join(f"{k} AS {v}" if v is not None else f"{k}" for k, v in with_parts.items())
    query = f"""
    WITH {node_alias}
    OPTIONAL MATCH path = {filter_str}
    WHERE {where_str}
    WITH {with_str}
    RETURN {to_return}
    ORDER BY branch_level DESC, froms[-1] DESC, froms[-2] DESC
    LIMIT 1
    """

    return query, params, prefix
