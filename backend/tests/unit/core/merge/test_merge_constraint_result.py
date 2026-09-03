"""Which constraint violations a merge keeps once diff conflicts are taken into account.

A conflict resolution reconciles the one field it is about, so a violation on that exact field is
dropped. The match is on the node and the field the conflict names, nothing broader: a conflict on a
schema node's property must not hide a violation on the data that property governs.
"""

from __future__ import annotations

from infrahub.core.constants import SchemaPathType
from infrahub.core.merge.constraints import ConflictedField, build_merge_constraint_result
from infrahub.core.path import SchemaPath
from infrahub.core.validators.model import SchemaViolation
from infrahub.core.validators.models.validate_migration import SchemaValidatorPathResponseData

WIDGET_UUID = "widget-1"
CODE_SCHEMA_ATTRIBUTE_UUID = "schema-attribute-code"
BRANCH = "branch1"


def _violation(node_id: str = WIDGET_UUID) -> SchemaViolation:
    return SchemaViolation(
        node_id=node_id,
        node_kind="TestingWidget",
        display_label="widget-one",
        full_display_label="TestingWidget widget-one",
        message=f"{node_id} does not match the regex",
    )


def _regex_response(*violations: SchemaViolation) -> SchemaValidatorPathResponseData:
    return SchemaValidatorPathResponseData(
        violations=list(violations),
        constraint_name="attribute.parameters.regex.update",
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE,
            schema_kind="TestingWidget",
            field_name="code",
            property_name="parameters.regex",
        ),
    )


def test_a_violation_with_no_conflict_is_kept() -> None:
    result = build_merge_constraint_result(
        responses=[_regex_response(_violation())], conflicted_fields=set(), branch=BRANCH
    )

    assert [violation.node_id for violation in result.violations] == [WIDGET_UUID]
    assert [(conflict.type, conflict.id, conflict.branch) for conflict in result.schema_conflicts] == [
        ("attribute.parameters.regex.update", WIDGET_UUID, BRANCH)
    ]


def test_a_conflict_on_the_same_node_and_field_drops_the_violation() -> None:
    conflicted = {ConflictedField(node_id=WIDGET_UUID, field_name="code")}

    result = build_merge_constraint_result(
        responses=[_regex_response(_violation())], conflicted_fields=conflicted, branch=BRANCH
    )

    assert result.violations == []
    assert result.schema_conflicts == []


def test_a_conflict_on_the_schema_property_does_not_hide_a_data_violation() -> None:
    """Both branches changed the regex and the user picked one; the data still has to satisfy it.

    The conflict lives on the ``SchemaAttribute`` node's ``parameters``, the violation on a widget's
    ``code``. They share nothing the match looks at, so resolving the schema conflict leaves the data
    check intact.
    """
    conflicted = {ConflictedField(node_id=CODE_SCHEMA_ATTRIBUTE_UUID, field_name="parameters")}

    result = build_merge_constraint_result(
        responses=[_regex_response(_violation())], conflicted_fields=conflicted, branch=BRANCH
    )

    assert [violation.node_id for violation in result.violations] == [WIDGET_UUID]


def test_only_the_conflicted_node_is_dropped_from_a_shared_response() -> None:
    conflicted = {ConflictedField(node_id=WIDGET_UUID, field_name="code")}

    result = build_merge_constraint_result(
        responses=[_regex_response(_violation(), _violation(node_id="widget-2"))],
        conflicted_fields=conflicted,
        branch=BRANCH,
    )

    assert [violation.node_id for violation in result.violations] == ["widget-2"]
