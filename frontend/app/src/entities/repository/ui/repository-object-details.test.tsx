import { beforeEach, describe, expect, it, vi } from "vitest";

import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { getRepositoryBranchStatusFromApi } from "@/entities/repository/api/get-repository-branch-status-from-api";
import { BRANCHES_LOAD_FAILED } from "@/entities/repository/ui/repository-branches-card/messages";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import {
  generateNodeAttributeWithMetadata,
  generateRelationshipNodeWithMetadata,
} from "../../../../tests/fake/node";
import { generatePermission } from "../../../../tests/fake/permission";
import { generateRepositoryBranchStatusPayloadBefore } from "../../../../tests/fake/repository";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../tests/fake/schema";
import { RepositoryObjectDetails } from "./repository-object-details";

vi.mock("@/entities/repository/api/get-repository-branch-status-from-api");

const apiMock = vi.mocked(getRepositoryBranchStatusFromApi);

const permission = generatePermission();

const CURRENT_BRANCH_NAME = generateBranch().name;

const repositoryWideAttributes = [
  generateAttributeSchema({
    name: "name",
    label: "Name",
    branch: "agnostic",
    order_weight: 1000,
  }),
  generateAttributeSchema({
    name: "location",
    label: "Location",
    branch: "agnostic",
    order_weight: 2000,
  }),
];

const branchScopedAttributes = [
  generateAttributeSchema({
    name: "sync_status",
    label: "Import status",
    branch: "local",
    order_weight: 3000,
  }),
  generateAttributeSchema({
    name: "commit",
    label: "Commit",
    branch: "local",
    order_weight: 4000,
  }),
];

const credentialRelationship = generateRelationshipSchema({
  name: "credential",
  label: "Credential",
  peer: "CoreCredential",
  kind: "Attribute",
  cardinality: "one",
  branch: "agnostic",
  order_weight: 5000,
});

const templateRelationship = generateRelationshipSchema({
  name: "template",
  label: "Template",
  peer: "CoreTemplate",
  kind: "Attribute",
  cardinality: "one",
  branch: "aware",
  order_weight: 6000,
});

const repositorySchema: ModelSchema = generateNodeSchema({
  kind: "CoreRepository",
  name: "Repository",
  namespace: "Core",
  label: "Repository",
  branch: "agnostic",
  inherit_from: ["CoreGenericRepository"],
  attributes: [...repositoryWideAttributes, ...branchScopedAttributes],
  relationships: [credentialRelationship, templateRelationship],
});

const objectData: NodeObjectWithMetadata = {
  id: "repository-1",
  display_label: "demo-repository",
  __typename: "CoreRepository",
  name: generateNodeAttributeWithMetadata({ value: "demo-repository" }),
  location: generateNodeAttributeWithMetadata({ value: "https://github.com/opsmill/demo" }),
  sync_status: generateNodeAttributeWithMetadata({ value: "in-sync" }),
  commit: generateNodeAttributeWithMetadata({ value: "abc1234" }),
  credential: generateRelationshipNodeWithMetadata({
    node: { id: "credential-1", display_label: "demo-credential", __typename: "CoreCredential" },
  }),
  template: generateRelationshipNodeWithMetadata({
    node: { id: "template-1", display_label: "demo-template", __typename: "CoreTemplate" },
  }),
};

beforeEach(() => {
  apiMock.mockResolvedValue({
    data: { InfrahubRepositoryBranchStatus: generateRepositoryBranchStatusPayloadBefore() },
  });
});

describe("RepositoryObjectDetails", () => {
  it("splits the details into a repository-wide card and a branch-scoped card named after the branch", async () => {
    const component = await render(
      <RepositoryObjectDetails
        objectSchema={repositorySchema}
        objectData={objectData}
        permission={permission}
      />
    );

    const repositoryWideCard = component.getByRole("region", { name: "Details" });
    const branchScopedCard = component.getByRole("region", {
      name: `On this branch ${CURRENT_BRANCH_NAME}`,
    });

    await expect.element(repositoryWideCard).toBeVisible();
    await expect.element(branchScopedCard).toBeVisible();

    await expect.element(repositoryWideCard.getByText("Name", { exact: true })).toBeVisible();
    await expect.element(repositoryWideCard.getByText("Location", { exact: true })).toBeVisible();
    await expect.element(branchScopedCard.getByText("Commit", { exact: true })).toBeVisible();
    await expect
      .element(branchScopedCard.getByText("Import status", { exact: true }))
      .toBeVisible();

    expect(repositoryWideCard.getByText("Commit", { exact: true }).elements()).toHaveLength(0);
    expect(branchScopedCard.getByText("Name", { exact: true }).elements()).toHaveLength(0);
  });

  it("reads repository-wide details, then the branch-scoped details, then the branches card", async () => {
    const component = await render(
      <RepositoryObjectDetails
        objectSchema={repositorySchema}
        objectData={objectData}
        permission={permission}
      />
    );

    const repositoryWideCard = component.getByRole("region", { name: "Details" }).element();
    const branchScopedCard = component
      .getByRole("region", { name: `On this branch ${CURRENT_BRANCH_NAME}` })
      .element();
    const branchesCardLocator = component.getByRole("region", { name: "Branches" });
    await expect.element(branchesCardLocator).toBeVisible();
    const branchesCard = branchesCardLocator.element();

    expect(repositoryWideCard.compareDocumentPosition(branchScopedCard)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING
    );
    expect(branchScopedCard.compareDocumentPosition(branchesCard)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING
    );
  });

  it("files an invented attribute by the branch support it declares, not by its name", async () => {
    const schemaWithInventedAttributes = generateNodeSchema({
      ...repositorySchema,
      attributes: [
        ...repositoryWideAttributes,
        generateAttributeSchema({
          name: "widget_realm",
          label: "Widget realm",
          branch: "agnostic",
          order_weight: 7000,
        }),
        generateAttributeSchema({
          name: "widget_mode",
          label: "Widget mode",
          branch: "aware",
          order_weight: 8000,
        }),
      ],
      relationships: [],
    });

    const component = await render(
      <RepositoryObjectDetails
        objectSchema={schemaWithInventedAttributes}
        objectData={{
          ...objectData,
          widget_realm: generateNodeAttributeWithMetadata({ value: "realm-one" }),
          widget_mode: generateNodeAttributeWithMetadata({ value: "mode-two" }),
        }}
        permission={permission}
      />
    );

    const repositoryWideCard = component.getByRole("region", { name: "Details" });
    const branchScopedCard = component.getByRole("region", {
      name: `On this branch ${CURRENT_BRANCH_NAME}`,
    });

    await expect
      .element(repositoryWideCard.getByText("Widget realm", { exact: true }))
      .toBeVisible();
    await expect.element(branchScopedCard.getByText("Widget mode", { exact: true })).toBeVisible();

    expect(repositoryWideCard.getByText("Widget mode", { exact: true }).elements()).toHaveLength(0);
    expect(branchScopedCard.getByText("Widget realm", { exact: true }).elements()).toHaveLength(0);
  });

  it("renders each relationship label exactly once across the two cards", async () => {
    const component = await render(
      <RepositoryObjectDetails
        objectSchema={repositorySchema}
        objectData={objectData}
        permission={permission}
      />
    );

    await expect.element(component.getByText("Credential", { exact: true })).toBeVisible();
    await expect.element(component.getByText("Template", { exact: true })).toBeVisible();

    expect(component.getByText("Credential", { exact: true }).elements()).toHaveLength(1);
    expect(component.getByText("Template", { exact: true }).elements()).toHaveLength(1);
  });

  it("renders no branch-scoped card when every field is repository-wide", async () => {
    const allRepositoryWideSchema = generateNodeSchema({
      ...repositorySchema,
      attributes: repositoryWideAttributes,
      relationships: [credentialRelationship],
    });

    const component = await render(
      <RepositoryObjectDetails
        objectSchema={allRepositoryWideSchema}
        objectData={objectData}
        permission={permission}
      />
    );

    await expect.element(component.getByRole("region", { name: "Details" })).toBeVisible();

    expect(component.getByText("On this branch", { exact: true }).elements()).toHaveLength(0);
    expect(
      component.getByRole("region", { name: `On this branch ${CURRENT_BRANCH_NAME}` }).elements()
    ).toHaveLength(0);
  });

  it("omits an attribute the viewed kind does not define instead of rendering an empty row", async () => {
    const readOnlySchema = generateNodeSchema({
      ...repositorySchema,
      kind: "CoreReadOnlyRepository",
      attributes: [
        ...repositoryWideAttributes,
        generateAttributeSchema({
          name: "ref",
          label: "Ref",
          branch: "aware",
          order_weight: 3000,
        }),
      ],
      relationships: [],
    });

    const component = await render(
      <RepositoryObjectDetails
        objectSchema={readOnlySchema}
        objectData={{ ...objectData, ref: generateNodeAttributeWithMetadata({ value: "v1.2.3" }) }}
        permission={permission}
      />
    );

    const branchScopedCard = component.getByRole("region", {
      name: `On this branch ${CURRENT_BRANCH_NAME}`,
    });

    await expect.element(branchScopedCard.getByText("Ref", { exact: true })).toBeVisible();
    await expect.element(branchScopedCard.getByText("v1.2.3", { exact: true })).toBeVisible();

    expect(component.getByText("Import status", { exact: true }).elements()).toHaveLength(0);
  });

  it("renders both details cards while the branches query is in a failed state", async () => {
    apiMock.mockRejectedValue(new Error("branch status unavailable"));

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
      .element(component.getByRole("region", { name: `On this branch ${CURRENT_BRANCH_NAME}` }))
      .toBeVisible();
    await expect.element(component.getByText("demo-repository", { exact: true })).toBeVisible();
  });

  it("names every value on both cards, with the branch name part of the branch-scoped card's accessible name", async () => {
    const component = await render(
      <RepositoryObjectDetails
        objectSchema={repositorySchema}
        objectData={objectData}
        permission={permission}
      />
    );

    const repositoryWideCard = component.getByRole("region", { name: "Details" });
    const branchScopedCard = component.getByRole("region", {
      name: `On this branch ${CURRENT_BRANCH_NAME}`,
    });

    await expect
      .element(repositoryWideCard.getByText("demo-repository", { exact: true }))
      .toBeVisible();
    await expect
      .element(repositoryWideCard.getByText("https://github.com/opsmill/demo", { exact: true }))
      .toBeVisible();
    await expect.element(branchScopedCard.getByText("in-sync", { exact: true })).toBeVisible();
    await expect.element(branchScopedCard.getByText("abc1234", { exact: true })).toBeVisible();

    expect(
      component.getByRole("region", { name: `On this branch ${CURRENT_BRANCH_NAME}` }).elements()
    ).toHaveLength(1);
  });
});
