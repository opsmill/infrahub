import { beforeEach, describe, expect, it, vi } from "vitest";

import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { getRepositoryBranchStatusFromApi } from "@/entities/repository/api/get-repository-branch-status-from-api";
import { BRANCHES_LOAD_FAILED } from "@/entities/repository/ui/repository-branches-card/messages";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

import { render } from "../../../../tests/components/render";
import { generateNodeAttributeWithMetadata } from "../../../../tests/fake/node";
import { generatePermission } from "../../../../tests/fake/permission";
import { generateRepositoryBranchStatusPayloadBefore } from "../../../../tests/fake/repository";
import { generateAttributeSchema, generateNodeSchema } from "../../../../tests/fake/schema";
import { RepositoryObjectDetails } from "./repository-object-details";

vi.mock("@/entities/repository/api/get-repository-branch-status-from-api");

// A cell that throws while rendering a row is the failure a rejected query cannot reproduce.
vi.mock("@/entities/repository/ui/repository-branches-card/cells/branch-name-cell", () => ({
  BranchNameCell: () => {
    throw new Error("branch name cell failed while rendering");
  },
}));

const apiMock = vi.mocked(getRepositoryBranchStatusFromApi);

const permission = generatePermission();

const repositorySchema: ModelSchema = generateNodeSchema({
  kind: "CoreRepository",
  name: "Repository",
  namespace: "Core",
  label: "Repository",
  branch: "agnostic",
  inherit_from: ["CoreGenericRepository"],
  attributes: [
    generateAttributeSchema({
      name: "name",
      label: "Name",
      branch: "agnostic",
      order_weight: 1000,
    }),
    generateAttributeSchema({
      name: "commit",
      label: "Commit",
      branch: "local",
      order_weight: 2000,
    }),
  ],
  relationships: [],
});

const objectData: NodeObjectWithMetadata = {
  id: "repository-1",
  display_label: "demo-repository",
  __typename: "CoreRepository",
  name: generateNodeAttributeWithMetadata({ value: "demo-repository" }),
  commit: generateNodeAttributeWithMetadata({ value: "abc1234" }),
};

beforeEach(() => {
  apiMock.mockResolvedValue({
    data: { InfrahubRepositoryBranchStatus: generateRepositoryBranchStatusPayloadBefore() },
  });
});

describe("RepositoryObjectDetails when the branches card throws during render", () => {
  it("still renders both details cards", async () => {
    const component = await render(
      <RepositoryObjectDetails
        objectSchema={repositorySchema}
        objectData={objectData}
        permission={permission}
      />
    );

    await expect.element(component.getByText(BRANCHES_LOAD_FAILED, { exact: true })).toBeVisible();

    await expect.element(component.getByRole("region", { name: "Details" })).toBeVisible();
    await expect
      .element(component.getByRole("region", { name: "On this branch test-branch" }))
      .toBeVisible();
    await expect.element(component.getByText("demo-repository", { exact: true })).toBeVisible();
    await expect.element(component.getByText("abc1234", { exact: true })).toBeVisible();
  });
});
