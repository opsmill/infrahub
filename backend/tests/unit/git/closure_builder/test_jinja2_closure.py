from __future__ import annotations

from pathlib import Path

from infrahub_sdk.schema.repository import InfrahubJinja2TransformConfig

from infrahub.git.closure_builder.jinja2_closure import Jinja2Closure


def _config(*, name: str, template_path: str) -> InfrahubJinja2TransformConfig:
    return InfrahubJinja2TransformConfig(
        name=name,
        query="any-query",
        template_path=Path(template_path),
    )


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_static_includes_imports_and_extends_are_resolved_transitively(tmp_path: Path) -> None:
    """A Jinja2 template's static references close transitively under ``include``/``import``/``extends``.

    The walker must reach every template that contributes content to the final
    render, not just the immediate references, so that an edit to a deeply
    transitive partial still triggers the correct regeneration.
    """
    _write(
        tmp_path,
        "templates/device.j2",
        "{% extends 'templates/base.j2' %}\n{% include 'templates/header.j2' %}\n",
    )
    _write(
        tmp_path,
        "templates/base.j2",
        "{% include 'templates/footer.j2' %}\n",
    )
    _write(tmp_path, "templates/header.j2", "header\n")
    _write(tmp_path, "templates/footer.j2", "{% import 'templates/macros.j2' as m %}\n")
    _write(tmp_path, "templates/macros.j2", "macro body\n")

    result = Jinja2Closure().build(
        transform_config=_config(name="device", template_path="templates/device.j2"),
        worktree_root=tmp_path,
    )

    assert result.dependencies == (
        "templates/base.j2",
        "templates/device.j2",
        "templates/footer.j2",
        "templates/header.j2",
        "templates/macros.j2",
    )
    assert result.complete is True
    assert result.unresolved == ()


def test_dynamic_include_produces_unresolved_and_marks_incomplete(tmp_path: Path) -> None:
    """A dynamic ``{% include some_var %}`` produces an unresolved reference and `complete=False`.

    The integrator cannot know what `some_var` will hold at render time, so the
    safe default is to record the unresolved site and fall back to a coarser gate
    until the user declares a covering ``watch.files`` for the transform.
    """
    _write(
        tmp_path,
        "templates/device.j2",
        "{% include some_var %}\n",
    )

    result = Jinja2Closure().build(
        transform_config=_config(name="device", template_path="templates/device.j2"),
        worktree_root=tmp_path,
    )

    assert result.complete is False
    assert result.dependencies == ("templates/device.j2",)
    assert len(result.unresolved) == 1
    assert result.unresolved[0].file == "templates/device.j2"


def test_multiple_unresolved_sites_are_all_recorded(tmp_path: Path) -> None:
    """Every unresolved reference is recorded, including those in transitively reached templates.

    The closure builder continues walking past `None` references so that operators
    see the full list of dynamic sites in a single import pass and can write a
    single covering ``watch.files`` declaration instead of repeatedly re-importing.
    """
    _write(
        tmp_path,
        "templates/device.j2",
        "{% include first_var %}\n{% include 'templates/sub.j2' %}\n{% include second_var %}\n",
    )
    _write(
        tmp_path,
        "templates/sub.j2",
        "{% include third_var %}\n",
    )

    result = Jinja2Closure().build(
        transform_config=_config(name="device", template_path="templates/device.j2"),
        worktree_root=tmp_path,
    )

    assert result.complete is False
    assert result.dependencies == ("templates/device.j2", "templates/sub.j2")
    unresolved_files = sorted(ref.file for ref in result.unresolved)
    assert unresolved_files == ["templates/device.j2", "templates/device.j2", "templates/sub.j2"]


def test_paths_are_canonicalized(tmp_path: Path) -> None:
    """Dependency paths are returned in the shared canonical form before storage.

    Without canonicalization the read-side set intersection at pipeline time
    would not align with the canonicalized diff entries; tests pin the form
    so future builder edits cannot bypass the canonicalizer.
    """
    _write(
        tmp_path,
        "templates/device.j2",
        "{% include './templates/header.j2' %}\n",
    )
    _write(tmp_path, "templates/header.j2", "header\n")

    result = Jinja2Closure().build(
        transform_config=_config(name="device", template_path="./templates/device.j2"),
        worktree_root=tmp_path,
    )

    assert result.dependencies == ("templates/device.j2", "templates/header.j2")


def test_dependencies_are_sorted_lexicographically(tmp_path: Path) -> None:
    """The returned dependency tuple is sorted, so byte-identical storage across re-imports is guaranteed.

    Stable ordering is the precondition that lets the diff layer skip emitting a
    node modification when the closure has not actually changed.
    """
    _write(
        tmp_path,
        "templates/device.j2",
        "{% include 'templates/zeta.j2' %}\n{% include 'templates/alpha.j2' %}\n",
    )
    _write(tmp_path, "templates/zeta.j2", "z")
    _write(tmp_path, "templates/alpha.j2", "a")

    result = Jinja2Closure().build(
        transform_config=_config(name="device", template_path="templates/device.j2"),
        worktree_root=tmp_path,
    )

    assert result.dependencies == ("templates/alpha.j2", "templates/device.j2", "templates/zeta.j2")


def test_missing_template_referenced_is_recorded_but_walk_continues(tmp_path: Path) -> None:
    """A static reference to a missing file is recorded as unresolved and the walk continues.

    If a missing reference were silently dropped, adding the file later would
    not pull it into the closure - the closure builder would not re-record
    it because nothing about the source template changed. Recording the
    miss surfaces the problem and lets the pipeline fall back to the
    coarser gate until the user resolves it.
    """
    _write(
        tmp_path,
        "templates/device.j2",
        "{% include 'templates/missing.j2' %}\n{% include 'templates/present.j2' %}\n",
    )
    _write(tmp_path, "templates/present.j2", "present\n")

    result = Jinja2Closure().build(
        transform_config=_config(name="device", template_path="templates/device.j2"),
        worktree_root=tmp_path,
    )

    assert "templates/device.j2" in result.dependencies
    assert "templates/present.j2" in result.dependencies
    assert "templates/missing.j2" not in result.dependencies
    assert result.complete is False
    assert any(
        ref.file == "templates/device.j2" and "templates/missing.j2" in ref.location for ref in result.unresolved
    )


def test_unreadable_entry_template_is_recorded_as_unresolved(tmp_path: Path) -> None:
    """An entry template that cannot be read is recorded as unresolved and flips `complete=False`.

    Silently dropping an unreadable entry template would leave the closure
    containing only the entry path with `complete=True`, which the regeneration
    gate trusts. The result would be a transform whose closure is missing every
    real dependency yet still gates on a single file. Recording the failure flips
    the trust bit so the pipeline falls back to the coarser gate.
    """
    result = Jinja2Closure().build(
        transform_config=_config(name="device", template_path="templates/missing_entry.j2"),
        worktree_root=tmp_path,
    )

    assert result.dependencies == ("templates/missing_entry.j2",)
    assert result.complete is False
    assert any(
        ref.file == "templates/missing_entry.j2" and ref.location == "template not readable"
        for ref in result.unresolved
    )


def test_entry_path_escaping_the_worktree_is_rejected(tmp_path: Path) -> None:
    """A `template_path` that resolves outside the worktree is rejected before any read.

    The entry path is user-controlled via `.infrahub.yml`. Without an early
    boundary check, a `template_path` like ``../../../etc/passwd`` would resolve
    outside the worktree and be read by the closure walker. The boundary check
    on the entry path mirrors the one applied to transitively-discovered
    references and short-circuits the walk before any I/O.
    """
    outside_dir = tmp_path.parent / "outside_worktree_entry"
    outside_dir.mkdir(exist_ok=True)
    (outside_dir / "secret.j2").write_text("secret\n", encoding="utf-8")

    worktree = tmp_path / "worktree"
    worktree.mkdir()

    result = Jinja2Closure().build(
        transform_config=_config(name="device", template_path="../outside_worktree_entry/secret.j2"),
        worktree_root=worktree,
    )

    assert result.dependencies == ()
    assert result.complete is False
    assert any("entry path escapes worktree" in ref.location for ref in result.unresolved)


def test_reference_escaping_the_worktree_is_recorded_as_unresolved(tmp_path: Path) -> None:
    """A reference that resolves outside the worktree root is recorded and not followed.

    Templates are user-controlled content and must not be allowed to pull
    arbitrary host filesystem files into the closure or, worse, to be read
    through during the closure walk. The walker validates each resolved
    reference against the worktree root and flags any escape attempt.
    """
    outside_dir = tmp_path.parent / "outside_worktree"
    outside_dir.mkdir(exist_ok=True)
    (outside_dir / "secret.j2").write_text("secret\n", encoding="utf-8")

    worktree = tmp_path / "worktree"
    _write(
        worktree,
        "templates/device.j2",
        "{% include '../../outside_worktree/secret.j2' %}\n",
    )

    result = Jinja2Closure().build(
        transform_config=_config(name="device", template_path="templates/device.j2"),
        worktree_root=worktree,
    )

    assert result.complete is False
    assert all("outside_worktree" not in entry for entry in result.dependencies)
    assert any("escapes worktree" in ref.location for ref in result.unresolved)
