from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema.schema_branch_computed import ComputedAttributes
from infrahub.core.schema.schema_branch_computed.jinja2 import RegisteredNodeComputedAttribute

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.core.schema.schema_branch_computed import ComputedAttributeTarget

LOCAL_KIND = "TestDevice"
REMOTE_KIND = "TestSite"


class TestCascadeWithExplicitUpdates:
    """Tests for chained dependency resolution when updates is a concrete list of field names."""

    def _make_chain_registry(self, make_target: Callable[..., ComputedAttributeTarget]) -> ComputedAttributes:
        """name -> label -> fqdn chain on a single kind."""
        label_target = make_target(kind=LOCAL_KIND, attr_name="label")
        fqdn_target = make_target(kind=LOCAL_KIND, attr_name="fqdn")
        return ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [label_target],
                        "label": [fqdn_target],
                    },
                ),
            },
        )

    def test_returns_full_chain(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        ca = self._make_chain_registry(make_target)
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        assert [r.attribute.name for r in results] == ["label", "fqdn"]

    def test_respects_dependency_order(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """label must come before fqdn since fqdn depends on label."""
        ca = self._make_chain_registry(make_target)
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        names = [r.attribute.name for r in results]
        assert names.index("label") < names.index("fqdn")

    def test_single_target_no_chain(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """When there's no chain, only the direct target is returned."""
        target = make_target(kind=LOCAL_KIND, attr_name="label")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={"name": [target]},
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        assert [r.attribute.name for r in results] == ["label"]

    def test_cascade_cycle_terminates(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """alpha -> beta -> alpha cycle does not loop forever."""
        target_alpha = make_target(kind=LOCAL_KIND, attr_name="alpha")
        target_beta = make_target(kind=LOCAL_KIND, attr_name="beta")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "beta": [target_alpha],
                        "alpha": [target_beta],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["alpha"])
        names = [r.attribute.name for r in results]
        assert len(names) == 2
        assert set(names) == {"alpha", "beta"}

    def test_cascade_diamond(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """Diamond: name -> label, name -> desc, label -> summary, desc -> summary."""
        label_target = make_target(kind=LOCAL_KIND, attr_name="label")
        desc_target = make_target(kind=LOCAL_KIND, attr_name="desc")
        summary_target = make_target(kind=LOCAL_KIND, attr_name="summary")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [label_target, desc_target],
                        "label": [summary_target],
                        "desc": [summary_target],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        names = [r.attribute.name for r in results]
        # summary appears exactly once despite two paths
        assert names.count("summary") == 1
        # summary comes after both label and desc
        assert names.index("summary") > names.index("label")
        assert names.index("summary") > names.index("desc")

    def test_cascade_mixed_direct_and_transitive(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """When name triggers both label and fqdn, but fqdn also depends on label,
        label must be recomputed before fqdn regardless of list order in local_fields."""
        label_target = make_target(kind=LOCAL_KIND, attr_name="label")
        fqdn_target = make_target(kind=LOCAL_KIND, attr_name="fqdn")
        # fqdn listed BEFORE label in the "name" entry to exercise wrong-order scenario
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [fqdn_target, label_target],
                        "label": [fqdn_target],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        names = [r.attribute.name for r in results]
        assert names.index("label") < names.index("fqdn")

    def test_cascade_skips_remote_targets(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """Remote targets (different kind) are excluded even with cascade."""
        local_target = make_target(kind=LOCAL_KIND, attr_name="label")
        remote_target = make_target(kind=REMOTE_KIND, attr_name="remote_label")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [local_target, remote_target],
                        "label": [make_target(kind=LOCAL_KIND, attr_name="fqdn")],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        result_kinds = {r.kind for r in results}
        assert REMOTE_KIND not in result_kinds

    def test_sibling_not_lost_when_wave_has_intra_dependency(
        self, make_target: Callable[..., ComputedAttributeTarget]
    ) -> None:
        """Regression: name -> [label, serial, fqdn] with label -> fqdn.

        serial is independent and must not be dropped when the wave splits
        label (prerequisite) from fqdn (dependent).
        """
        label_target = make_target(kind=LOCAL_KIND, attr_name="label")
        serial_target = make_target(kind=LOCAL_KIND, attr_name="serial")
        fqdn_target = make_target(kind=LOCAL_KIND, attr_name="fqdn")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [label_target, serial_target, fqdn_target],
                        "label": [fqdn_target],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        names = [r.attribute.name for r in results]
        assert "serial" in names
        assert "label" in names
        assert "fqdn" in names
        # label before fqdn (dependency), serial anywhere but present
        assert names.index("label") < names.index("fqdn")

    def test_long_chain_three_levels(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """name -> label -> fqdn -> hostname: 3-hop chain."""
        label_target = make_target(kind=LOCAL_KIND, attr_name="label")
        fqdn_target = make_target(kind=LOCAL_KIND, attr_name="fqdn")
        hostname_target = make_target(kind=LOCAL_KIND, attr_name="hostname")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [label_target],
                        "label": [fqdn_target],
                        "fqdn": [hostname_target],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        names = [r.attribute.name for r in results]
        assert names == ["label", "fqdn", "hostname"]

    def test_three_node_cycle(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """alpha -> beta -> gamma -> alpha: 3-node cycle terminates."""
        alpha = make_target(kind=LOCAL_KIND, attr_name="alpha")
        beta = make_target(kind=LOCAL_KIND, attr_name="beta")
        gamma = make_target(kind=LOCAL_KIND, attr_name="gamma")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "alpha": [beta],
                        "beta": [gamma],
                        "gamma": [alpha],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["alpha"])
        names = [r.attribute.name for r in results]
        assert len(names) == 3
        assert set(names) == {"alpha", "beta", "gamma"}

    def test_multiple_updates_dedup(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """updates=['name', 'desc'] both trigger label: label appears once."""
        label_target = make_target(kind=LOCAL_KIND, attr_name="label")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [label_target],
                        "desc": [label_target],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name", "desc"])
        assert len(results) == 1
        assert results[0].attribute.name == "label"

    def test_update_unknown_field(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """updates=['nonexistent'] triggers nothing."""
        target = make_target(kind=LOCAL_KIND, attr_name="label")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={"name": [target]},
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["nonexistent"])
        assert results == []

    def test_independent_branches_from_single_update(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """name -> [label, desc], label -> summary, desc -> footer.

        summary and footer are independent leaves on separate branches.
        """
        label_target = make_target(kind=LOCAL_KIND, attr_name="label")
        desc_target = make_target(kind=LOCAL_KIND, attr_name="desc")
        summary_target = make_target(kind=LOCAL_KIND, attr_name="summary")
        footer_target = make_target(kind=LOCAL_KIND, attr_name="footer")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [label_target, desc_target],
                        "label": [summary_target],
                        "desc": [footer_target],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        names = [r.attribute.name for r in results]
        assert set(names) == {"label", "desc", "summary", "footer"}
        assert names.index("label") < names.index("summary")
        assert names.index("desc") < names.index("footer")

    def test_asymmetric_diamond(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """name -> aaa -> bbb -> ddd and name -> ccc -> ddd: ddd after all deps despite path-length asymmetry."""
        aaa = make_target(kind=LOCAL_KIND, attr_name="aaa")
        bbb = make_target(kind=LOCAL_KIND, attr_name="bbb")
        ccc = make_target(kind=LOCAL_KIND, attr_name="ccc")
        ddd = make_target(kind=LOCAL_KIND, attr_name="ddd")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [aaa, ccc],
                        "aaa": [bbb],
                        "bbb": [ddd],
                        "ccc": [ddd],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        names = [r.attribute.name for r in results]
        assert names.count("ddd") == 1
        assert names.index("aaa") < names.index("bbb")
        assert names.index("bbb") < names.index("ddd")
        assert names.index("ccc") < names.index("ddd")

    def test_three_way_intra_wave_chain(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """name -> [aaa, bbb, ccc] with aaa -> bbb -> ccc: all emitted in correct order."""
        aaa = make_target(kind=LOCAL_KIND, attr_name="aaa")
        bbb = make_target(kind=LOCAL_KIND, attr_name="bbb")
        ccc = make_target(kind=LOCAL_KIND, attr_name="ccc")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [aaa, bbb, ccc],
                        "aaa": [bbb],
                        "bbb": [ccc],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        names = [r.attribute.name for r in results]
        assert set(names) == {"aaa", "bbb", "ccc"}
        assert names.index("aaa") < names.index("bbb")
        assert names.index("bbb") < names.index("ccc")


class TestCascadeWithFullSave:
    """Tests for chained dependency resolution when updates is None or empty (full save).

    Regression suite: get_local_jinja2_targets must preserve topological ordering
    even when no explicit field list is provided.
    """

    def test_full_save_preserves_dependency_order(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """updates=None must return chained targets in dependency order.

        The local_fields dict is deliberately ordered so that the dependent target (fqdn)
        appears before its prerequisite (label) in iteration order, exposing any code path
        that returns targets in raw dict order instead of topological order.
        """
        label_target = make_target(kind=LOCAL_KIND, attr_name="label")
        fqdn_target = make_target(kind=LOCAL_KIND, attr_name="fqdn")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        # fqdn depends on label, but "label" key (which produces fqdn)
                        # is listed BEFORE "name" key (which produces label),
                        # so raw dict iteration yields fqdn before label.
                        "label": [fqdn_target],
                        "name": [label_target],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=None)
        names = [r.attribute.name for r in results]
        assert len(names) == len(set(names)), f"Duplicate targets detected: {names}"
        assert set(names) == {"label", "fqdn"}
        assert names.index("label") < names.index("fqdn")

    def test_full_save_skips_remote_targets(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """updates=None must exclude remote targets from local results."""
        local_target = make_target(kind=LOCAL_KIND, attr_name="label")
        remote_target = make_target(kind=REMOTE_KIND, attr_name="remote_label")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [local_target, remote_target],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=None)
        assert len(results) == 1
        assert results[0].kind == LOCAL_KIND

    def test_full_save_empty_list_preserves_dependency_order(
        self, make_target: Callable[..., ComputedAttributeTarget]
    ) -> None:
        """updates=[] (falsy like None) must also preserve dependency order."""
        label_target = make_target(kind=LOCAL_KIND, attr_name="label")
        fqdn_target = make_target(kind=LOCAL_KIND, attr_name="fqdn")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "label": [fqdn_target],
                        "name": [label_target],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=[])
        names = [r.attribute.name for r in results]
        assert len(names) == len(set(names)), f"Duplicate targets detected: {names}"
        assert set(names) == {"label", "fqdn"}
        assert names.index("label") < names.index("fqdn")

    def test_full_save_returns_all_local_targets(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """updates=None returns all local targets, not just those reachable from a subset."""
        local_target = make_target(kind=LOCAL_KIND, attr_name="label")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={"name": [local_target]},
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=None)
        assert len(results) == 1
        assert results[0].attribute.name == "label"
