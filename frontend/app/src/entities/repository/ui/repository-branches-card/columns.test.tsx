import { describe, expect, it } from "vitest";

import { DataTable } from "@/shared/components/table/data-table";
import { COLUMN_MAX_WIDTH } from "@/shared/components/table/style";

import {
  mapRepositoryBranchStatusPage,
  type RepositoryBranchStatusRow,
} from "@/entities/repository/domain/model/repository-branch-status";
import {
  branchesGridTemplateColumns,
  getRepositoryBranchesColumns,
} from "@/entities/repository/ui/repository-branches-card/columns";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

import { render } from "../../../../../tests/components/render";
import { generateDropdown, generateInventedDropdown } from "../../../../../tests/fake/dropdown";
import {
  generateRepositoryBranchStatus,
  generateRepositoryBranchStatusPage,
  type RepositoryBranchStatusWire,
} from "../../../../../tests/fake/repository";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../tests/fake/schema";

const syncStatusAttribute = generateAttributeSchema({
  name: "sync_status",
  kind: "Dropdown",
  label: "Sync status",
});

const commitAttribute = generateAttributeSchema({ name: "commit", label: "Commit" });

const refAttribute = generateAttributeSchema({ name: "ref", label: "Ref" });

const repositorySchema: ModelSchema = generateNodeSchema({
  name: "Repository",
  namespace: "Core",
  attributes: [syncStatusAttribute, commitAttribute],
  relationships: [],
});

const readOnlyRepositorySchema: ModelSchema = generateNodeSchema({
  name: "ReadOnlyRepository",
  namespace: "Core",
  attributes: [syncStatusAttribute, commitAttribute, refAttribute],
  relationships: [],
});

// The CSSOM rewrites an authored hex colour as `rgb(…)`, so the fixture value has to go through the
// same normalisation before it can be compared.
const asRenderedColour = (colour: string): string => {
  const probe = document.createElement("span");
  probe.style.backgroundColor = colour;
  return probe.style.backgroundColor;
};

const toRows = (nodes: RepositoryBranchStatusWire[]): RepositoryBranchStatusRow[] =>
  mapRepositoryBranchStatusPage(generateRepositoryBranchStatusPage({ rows: nodes })).rows;

const renderTable = (schema: ModelSchema, nodes: RepositoryBranchStatusWire[]) =>
  render(
    <DataTable
      columns={getRepositoryBranchesColumns(schema)}
      data={toRows(nodes)}
      gridTemplateColumns={branchesGridTemplateColumns}
      semanticTable
    />
  );

describe("getRepositoryBranchesColumns", () => {
  it("shows the branch name, its sync status and its imported commit on each row", async () => {
    // GIVEN
    const nodes = [
      generateRepositoryBranchStatus({
        name: { value: "feature-auth" },
        is_default: { value: false },
        commit: { value: "8f3c2a1d9b4e7c05a2f1e6d3b8074c5a19fe2b6d" },
        sync_status: generateDropdown({ label: "In sync" }),
      }),
    ];

    // WHEN
    const component = await renderTable(repositorySchema, nodes);
    const row = component.getByRole("row", { name: /feature-auth/ });

    // THEN
    await expect.element(row.getByRole("link", { name: "feature-auth" })).toBeVisible();
    await expect.element(row.getByText("In sync", { exact: true })).toBeVisible();
    await expect.element(row.getByText("8f3c2a1", { exact: true })).toBeVisible();
  });

  it("marks only the default branch's row as the default", async () => {
    // GIVEN
    const nodes = [
      generateRepositoryBranchStatus({ name: { value: "main" }, is_default: { value: true } }),
      generateRepositoryBranchStatus({ name: { value: "staging" }, is_default: { value: false } }),
    ];

    // WHEN
    const component = await renderTable(repositorySchema, nodes);

    // THEN
    await expect
      .element(component.getByRole("row", { name: /main/ }).getByText("default", { exact: true }))
      .toBeVisible();
    expect(
      component
        .getByRole("row", { name: /staging/ })
        .getByText("default", { exact: true })
        .elements()
    ).toHaveLength(0);
  });

  it("takes each header from the schema's own label", async () => {
    // GIVEN
    const renamedSchema: ModelSchema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "sync_status", kind: "Dropdown", label: "Git state" }),
        commitAttribute,
      ],
      relationships: [],
    });

    // WHEN
    const component = await renderTable(renamedSchema, [generateRepositoryBranchStatus()]);

    // THEN
    await expect.element(component.getByText("Git state", { exact: true })).toBeVisible();
    expect(component.getByText("Sync status", { exact: true }).elements()).toHaveLength(0);
  });

  it("renders the chip label and colour the payload supplies", async () => {
    // GIVEN
    const invented = generateInventedDropdown();
    const nodes = [
      generateRepositoryBranchStatus({ name: { value: "spike" }, sync_status: invented }),
    ];

    // WHEN
    const component = await renderTable(repositorySchema, nodes);
    const chip = component
      .getByRole("row", { name: /spike/ })
      .getByText("Quarantined", { exact: true });

    // THEN
    await expect.element(chip).toBeVisible();
    expect(chip.element().style.backgroundColor).toBe(asRenderedColour(invented.color ?? ""));
  });

  it("leaves the ref column out of a schema that does not declare one", async () => {
    // WHEN
    const component = await renderTable(repositorySchema, [generateRepositoryBranchStatus()]);

    // THEN
    expect(component.getByText("Ref", { exact: true }).elements()).toHaveLength(0);
  });

  it("shows the ref a branch tracks when the schema declares one", async () => {
    // GIVEN
    const nodes = [
      generateRepositoryBranchStatus({
        name: { value: "main" },
        ref: { value: "refs/tags/v1.4.2" },
      }),
    ];

    // WHEN
    const component = await renderTable(readOnlyRepositorySchema, nodes);

    // THEN
    await expect.element(component.getByText("Ref", { exact: true })).toBeVisible();
    await expect
      .element(component.getByRole("row", { name: /main/ }).getByText("refs/tags/v1.4.2"))
      .toBeVisible();
  });

  it("renders no row-action control", async () => {
    // WHEN
    const component = await renderTable(repositorySchema, [generateRepositoryBranchStatus()]);

    // THEN
    expect(component.getByRole("row").getByRole("button").elements()).toHaveLength(0);
  });

  it("reserves no trailing row-action track", () => {
    // THEN
    expect(branchesGridTemplateColumns(3)).toBe(`repeat(2, fit-content(${COLUMN_MAX_WIDTH})) 1fr`);
    expect(branchesGridTemplateColumns(4)).not.toContain("2.5rem");
  });

  it("emits a single track rather than an empty repeat for a lone column", () => {
    // THEN
    expect(branchesGridTemplateColumns(1)).toBe("1fr");
  });
});
