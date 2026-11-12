import { describe, expect, it } from "vitest";

import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { ObjectDetailsCard } from "@/entities/nodes/object/ui/object-details/object-details-card";

import { render } from "../../../../../../tests/components/render";
import { generateNodeAttributeWithMetadata } from "../../../../../../tests/fake/node";
import { generatePermission } from "../../../../../../tests/fake/permission";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../../tests/fake/schema";

const permission = generatePermission();

const lacpSection = { name: "lacp", label: "LACP", collapsible: true, collapsed: false };

const profileSection = {
  name: "builtin_profile",
  label: "Profile",
  description: "Name and priority of the profile",
  collapsible: false,
  collapsed: false,
};

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

const schemaWithExtraField = generateNodeSchema({
  attributes: [
    generateAttributeSchema({ name: "commit", label: "Commit", order_weight: 1000 }),
    generateAttributeSchema({
      name: "internal_status",
      label: "Internal status",
      order_weight: 2000,
      display: "extra",
    }),
  ],
  relationships: [],
});

const objectDataWithExtraField: NodeObjectWithMetadata = {
  ...objectData,
  internal_status: generateNodeAttributeWithMetadata({ value: "active" }),
};

describe("ObjectDetailsCard", () => {
  it("names itself 'Details' and carries the shared test id when given neither", async () => {
    const component = await render(
      <ObjectDetailsCard
        objectSchema={schemaWithCommit}
        objectData={objectData}
        permission={permission}
      />
    );

    await expect.element(component.getByRole("region", { name: "Details" })).toBeVisible();
    await expect.element(component.getByTestId("object-details")).toBeVisible();
  });

  it("takes its accessible name from the text of a title made of several elements", async () => {
    const component = await render(
      <ObjectDetailsCard
        title={
          <>
            On this branch
            <span>main</span>
          </>
        }
        objectSchema={schemaWithCommit}
        objectData={objectData}
        permission={permission}
      />
    );

    await expect
      .element(component.getByRole("region", { name: "On this branch main" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("heading", { level: 2, name: "On this branch main" }))
      .toBeVisible();
  });

  it("renders the fields of the schema it is given", async () => {
    const component = await render(
      <ObjectDetailsCard
        objectSchema={schemaWithCommit}
        objectData={objectData}
        permission={permission}
      />
    );

    await expect.element(component.getByText("Commit", { exact: true })).toBeVisible();
  });

  it("gives two cards on the same page distinct accessible names", async () => {
    const component = await render(
      <>
        <ObjectDetailsCard
          objectSchema={schemaWithCommit}
          objectData={objectData}
          permission={permission}
        />
        <ObjectDetailsCard
          title="On this branch"
          objectSchema={schemaWithCommit}
          objectData={objectData}
          permission={permission}
        />
      </>
    );

    await expect.element(component.getByRole("region", { name: "Details" })).toBeVisible();
    await expect.element(component.getByRole("region", { name: "On this branch" })).toBeVisible();
  });

  it("keeps the extra fields behind a toggle", async () => {
    // GIVEN a schema carrying a field marked for the extra tier
    const component = await render(
      <ObjectDetailsCard
        objectSchema={schemaWithExtraField}
        objectData={objectDataWithExtraField}
        permission={permission}
      />
    );

    // THEN it is hidden until asked for, and the toggle is there to ask
    expect(component.getByText("Internal status", { exact: true }).elements()).toHaveLength(0);

    // WHEN
    await component.getByRole("button", { name: "Extra" }).click();

    // THEN
    await expect.element(component.getByText("Internal status", { exact: true })).toBeVisible();
  });

  it("offers no extra toggle for a schema that has no extra field", async () => {
    const component = await render(
      <ObjectDetailsCard
        objectSchema={schemaWithCommit}
        objectData={objectData}
        permission={permission}
      />
    );

    await expect.element(component.getByText("Commit", { exact: true })).toBeVisible();
    expect(component.getByRole("button", { name: "Extra" }).elements()).toHaveLength(0);
  });

  it("starts collapsed when its section is collapsed and expands when the header button is pressed", async () => {
    const component = await render(
      <ObjectDetailsCard
        section={{ ...lacpSection, collapsed: true }}
        objectSchema={schemaWithCommit}
        objectData={objectData}
        permission={permission}
      />
    );

    await expect.element(component.getByRole("region", { name: "LACP" })).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "LACP" }))
      .toHaveAttribute("aria-expanded", "false");
    await expect.element(component.getByText("Commit", { exact: true })).not.toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "LACP" }).click();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "LACP" }))
      .toHaveAttribute("aria-expanded", "true");
    await expect.element(component.getByText("Commit", { exact: true })).toBeVisible();
  });

  it("has no collapse button and stays expanded when its section is not collapsible", async () => {
    const component = await render(
      <ObjectDetailsCard
        section={{ ...profileSection, collapsed: true }}
        objectSchema={schemaWithExtraField}
        objectData={objectDataWithExtraField}
        permission={permission}
      />
    );

    const card = component.getByRole("region", { name: "Profile" });
    await expect.element(card).toHaveAttribute("data-testid", "object-details-section");
    await expect.element(card).toHaveAttribute("data-section", "builtin_profile");
    await expect.element(component.getByText("Name and priority of the profile")).toBeVisible();
    expect(component.getByRole("button", { name: "Profile" }).elements()).toHaveLength(0);
    await expect.element(component.getByText("Commit", { exact: true })).toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "Extra" }).click();

    // THEN
    await expect.element(component.getByText("Internal status", { exact: true })).toBeVisible();
  });

  it("has no button in its title when given no section", async () => {
    const component = await render(
      <ObjectDetailsCard
        title="LACP"
        objectSchema={schemaWithCommit}
        objectData={objectData}
        permission={permission}
      />
    );

    await expect.element(component.getByRole("region", { name: "LACP" })).toBeVisible();
    expect(component.getByRole("button", { name: "LACP" }).elements()).toHaveLength(0);
    await expect.element(component.getByText("Commit", { exact: true })).toBeVisible();
  });

  it("shows the description under the title outside the button and points aria-describedby at it", async () => {
    const component = await render(
      <ObjectDetailsCard
        section={{ ...lacpSection, description: "Link aggregation settings" }}
        objectSchema={schemaWithCommit}
        objectData={objectData}
        permission={permission}
      />
    );

    const description = component.getByText("Link aggregation settings");
    await expect.element(description).toBeVisible();
    await expect.element(component.getByRole("region", { name: "LACP" })).toBeVisible();
    await expect.element(component.getByRole("heading", { level: 2, name: "LACP" })).toBeVisible();

    const trigger = component.getByRole("button", { name: "LACP" });
    await expect.element(trigger).toHaveAccessibleDescription("Link aggregation settings");
    expect(trigger.element().contains(description.element())).toBe(false);
    expect(
      component.getByRole("heading", { level: 2 }).element().contains(description.element())
    ).toBe(false);
  });

  it("shows the Extra button only when the schema it receives has an extra field", async () => {
    const component = await render(
      <>
        <ObjectDetailsCard
          section={lacpSection}
          objectSchema={schemaWithExtraField}
          objectData={objectDataWithExtraField}
          permission={permission}
        />
        <ObjectDetailsCard
          section={{ name: "layer2", label: "Layer 2", collapsible: true, collapsed: false }}
          objectSchema={schemaWithCommit}
          objectData={objectData}
          permission={permission}
        />
      </>
    );

    const lacp = component.getByRole("region", { name: "LACP" });
    const layer2 = component.getByRole("region", { name: "Layer 2" });
    await expect.element(lacp.getByRole("button", { name: "Extra" })).toBeVisible();
    expect(layer2.getByRole("button", { name: "Extra" }).elements()).toHaveLength(0);

    // WHEN
    await lacp.getByRole("button", { name: "Extra" }).click();

    // THEN
    await expect.element(lacp.getByText("Internal status", { exact: true })).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "LACP" }))
      .toHaveAttribute("aria-expanded", "true");
  });

  it("hides the Extra button while the card is collapsed", async () => {
    // GIVEN a collapsed card whose schema has an extra field
    const component = await render(
      <ObjectDetailsCard
        section={{ ...lacpSection, collapsed: true }}
        objectSchema={schemaWithExtraField}
        objectData={objectDataWithExtraField}
        permission={permission}
      />
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "LACP" })).toBeVisible();
    expect(component.getByRole("button", { name: "Extra" }).elements()).toHaveLength(0);

    // WHEN
    await component.getByRole("button", { name: "LACP" }).click();

    // THEN
    await expect.element(component.getByRole("button", { name: "Extra" })).toBeVisible();
  });

  it("carries the section test id and the section name when given a section", async () => {
    const component = await render(
      <ObjectDetailsCard
        section={lacpSection}
        objectSchema={schemaWithCommit}
        objectData={objectData}
        permission={permission}
      />
    );

    const card = component.getByTestId("object-details-section");
    await expect.element(card).toHaveAttribute("data-section", "lacp");
    expect(card.element()).toBe(component.getByRole("region", { name: "LACP" }).element());
    expect(component.getByTestId("object-details").elements()).toHaveLength(0);
  });

  it("shows only the fields it is given by name", async () => {
    const component = await render(
      <ObjectDetailsCard
        fieldNames={["commit"]}
        objectSchema={schemaWithExtraField}
        objectData={objectDataWithExtraField}
        permission={permission}
      />
    );

    await expect.element(component.getByText("Commit", { exact: true })).toBeVisible();
    expect(component.getByRole("button", { name: "Extra" }).elements()).toHaveLength(0);
  });
});
