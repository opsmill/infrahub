import { describe, expect, it } from "vitest";

import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";

import { render } from "../../../../tests/components/render";
import { generateNodeAttributeWithMetadata } from "../../../../tests/fake/node";
import { generatePermission } from "../../../../tests/fake/permission";
import { generateAttributeSchema, generateNodeSchema } from "../../../../tests/fake/schema";
import { RepositoryDetailsCard } from "./repository-details-card";

const permission = generatePermission();

const schemaWithCommit = generateNodeSchema({
  attributes: [generateAttributeSchema({ name: "commit", label: "Commit", order_weight: 1000 })],
  relationships: [],
});

const objectData: NodeObjectWithMetadata = {
  id: "repository-1",
  display_label: "Test repository",
  __typename: "CoreRepository",
  commit: generateNodeAttributeWithMetadata({ value: "abc1234" }),
};

describe("RepositoryDetailsCard", () => {
  it("names the card by its title when no caption is given", async () => {
    const component = await render(
      <RepositoryDetailsCard
        title="Details"
        testId="repository-details"
        objectSchema={schemaWithCommit}
        objectData={objectData}
        permission={permission}
      />
    );

    await expect.element(component.getByRole("region", { name: "Details" })).toBeVisible();
  });

  it("renders the caption beneath the title and includes it in the card's accessible name", async () => {
    const component = await render(
      <RepositoryDetailsCard
        title="On this branch"
        caption="main"
        testId="repository-branch-details"
        objectSchema={schemaWithCommit}
        objectData={objectData}
        permission={permission}
      />
    );

    await expect
      .element(component.getByRole("region", { name: "On this branch main" }))
      .toBeVisible();

    const heading = component.getByRole("heading", { level: 2, name: "On this branch" }).element();
    expect(heading.nextElementSibling?.textContent).toBe("main");
  });

  it("renders the fields of the schema it is given", async () => {
    const component = await render(
      <RepositoryDetailsCard
        title="Details"
        testId="repository-details"
        objectSchema={schemaWithCommit}
        objectData={objectData}
        permission={permission}
      />
    );

    await expect.element(component.getByText("Commit", { exact: true })).toBeVisible();
  });

  it("renders nothing when the schema has no attributes and no relationships", async () => {
    const component = await render(
      <RepositoryDetailsCard
        title="On this branch"
        caption="main"
        testId="repository-branch-details"
        objectSchema={generateNodeSchema({ attributes: [], relationships: [] })}
        objectData={objectData}
        permission={permission}
      />
    );

    expect(component.getByRole("region").elements()).toHaveLength(0);
    expect(component.getByRole("heading").elements()).toHaveLength(0);
  });

  it("gives two cards on the same page distinct accessible names", async () => {
    const component = await render(
      <>
        <RepositoryDetailsCard
          title="Details"
          testId="repository-details"
          objectSchema={schemaWithCommit}
          objectData={objectData}
          permission={permission}
        />
        <RepositoryDetailsCard
          title="On this branch"
          caption="main"
          testId="repository-branch-details"
          objectSchema={schemaWithCommit}
          objectData={objectData}
          permission={permission}
        />
      </>
    );

    await expect.element(component.getByRole("region", { name: "Details" })).toBeVisible();
    await expect
      .element(component.getByRole("region", { name: "On this branch main" }))
      .toBeVisible();
  });
});
