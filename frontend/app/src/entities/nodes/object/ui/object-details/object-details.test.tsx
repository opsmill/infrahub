import { beforeEach, describe, expect, it, vi } from "vitest";

import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { ObjectDetails } from "@/entities/nodes/object/ui/object-details/object-details";
import { getRepositoryBranchStatusFromApi } from "@/entities/repository/api/get-repository-branch-status-from-api";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

import { render } from "../../../../../../tests/components/render";
import { generateNodeAttributeWithMetadata } from "../../../../../../tests/fake/node";
import { generatePermission } from "../../../../../../tests/fake/permission";
import { generateRepositoryBranchStatusPayloadBefore } from "../../../../../../tests/fake/repository";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../../tests/fake/schema";

vi.mock("@/entities/repository/api/get-repository-branch-status-from-api");

const apiMock = vi.mocked(getRepositoryBranchStatusFromApi);

const permission = generatePermission();

const attributes = [
  generateAttributeSchema({ name: "name", label: "Name", branch: "agnostic", order_weight: 1000 }),
  generateAttributeSchema({ name: "commit", label: "Commit", branch: "local", order_weight: 2000 }),
];

const tagSchema: ModelSchema = generateNodeSchema({
  kind: "BuiltinTag",
  name: "Tag",
  namespace: "Builtin",
  label: "Tag",
  branch: "aware",
  inherit_from: [],
  attributes,
  relationships: [],
});

const repositorySchema: ModelSchema = generateNodeSchema({
  kind: "CoreRepository",
  name: "Repository",
  namespace: "Core",
  label: "Repository",
  branch: "agnostic",
  inherit_from: ["CoreGenericRepository"],
  attributes,
  relationships: [],
});

const readOnlyRepositorySchema: ModelSchema = generateNodeSchema({
  ...repositorySchema,
  kind: "CoreReadOnlyRepository",
  name: "ReadOnlyRepository",
  label: "Read-only repository",
});

const objectData: NodeObjectWithMetadata = {
  id: "object-1",
  display_label: "demo-object",
  __typename: "BuiltinTag",
  name: generateNodeAttributeWithMetadata({ value: "demo-object" }),
  commit: generateNodeAttributeWithMetadata({ value: "abc1234" }),
};

beforeEach(() => {
  apiMock.mockResolvedValue({
    data: { InfrahubRepositoryBranchStatus: generateRepositoryBranchStatusPayloadBefore() },
  });
});

describe("ObjectDetails repository kind gate", () => {
  it("renders a single details card for a non-repository kind", async () => {
    const component = await render(
      <ObjectDetails objectSchema={tagSchema} objectData={objectData} permission={permission} />
    );

    await expect.element(component.getByText("Details", { exact: true })).toBeVisible();
    await expect.element(component.getByText("Name", { exact: true })).toBeVisible();
    await expect.element(component.getByText("Commit", { exact: true })).toBeVisible();

    expect(component.getByText("Details", { exact: true }).elements()).toHaveLength(1);
    expect(component.getByText("On this branch", { exact: true }).elements()).toHaveLength(0);
    expect(component.getByRole("region", { name: "Details" }).elements()).toHaveLength(0);
  });

  it("renders the two-card split for the read-write repository kind", async () => {
    const component = await render(
      <ObjectDetails
        objectSchema={repositorySchema}
        objectData={{ ...objectData, __typename: "CoreRepository" }}
        permission={permission}
      />
    );

    await expect.element(component.getByRole("region", { name: "Details" })).toBeVisible();
    await expect
      .element(component.getByRole("region", { name: "On this branch test-branch" }))
      .toBeVisible();
  });

  it("renders the two-card split for a kind that inherits from the repository generic", async () => {
    const component = await render(
      <ObjectDetails
        objectSchema={readOnlyRepositorySchema}
        objectData={{ ...objectData, __typename: "CoreReadOnlyRepository" }}
        permission={permission}
      />
    );

    await expect.element(component.getByRole("region", { name: "Details" })).toBeVisible();
    await expect
      .element(component.getByRole("region", { name: "On this branch test-branch" }))
      .toBeVisible();
  });
});
