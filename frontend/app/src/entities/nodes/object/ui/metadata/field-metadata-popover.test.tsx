import { beforeEach, describe, expect, it } from "vitest";

import { store } from "@/shared/stores";

import type { NodeRelationshipMetadata } from "@/entities/nodes/object/domain/model/node";
import {
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../tests/components/render";
import {
  generateNodeSchema,
  generateProfileSchema,
  generateTemplateSchema,
} from "../../../../../../tests/fake/schema";
import { FieldMetadataPopover } from "./field-metadata-popover";

describe("FieldMetadataPopover", () => {
  const emptyMetadata: NodeRelationshipMetadata = {
    updated_at: null,
    source: null,
    owner: null,
    is_protected: false,
  };

  beforeEach(() => {
    store.set(nodeSchemasAtom, [
      generateNodeSchema({ kind: "TestPeer", name: "Peer", namespace: "Test" }),
      generateNodeSchema({ kind: "CoreAccount", name: "Account", namespace: "Core" }),
    ]);
    store.set(profileSchemasAtom, [
      generateProfileSchema({ kind: "ProfileTestPeer", name: "TestPeer", namespace: "Profile" }),
    ]);
    store.set(templateSchemasAtom, [
      generateTemplateSchema({ kind: "TemplateTestPeer", name: "TestPeer", namespace: "Template" }),
    ]);
  });

  const openPopover = async (metadata: NodeRelationshipMetadata) => {
    const component = await render(<FieldMetadataPopover metadata={metadata} />);
    await component.getByRole("button", { name: "View metadata" }).click();
    return component;
  };

  it("shows a dash for each value the field does not have", async () => {
    // WHEN
    const component = await openPopover(emptyMetadata);

    // THEN
    await expect.element(component.getByText("Source")).toBeVisible();
    await expect.element(component.getByText("Owner")).toBeVisible();
    expect(component.getByText("-").elements()).toHaveLength(4);
    await expect.element(component.getByText("False")).toBeVisible();
  });

  it("links the source and the owner to their objects", async () => {
    // WHEN
    const component = await openPopover({
      ...emptyMetadata,
      source: { id: "peer-1", display_label: "Peer One", __typename: "TestPeer" },
      owner: { id: "account-1", display_label: "Ops Team", __typename: "CoreAccount" },
    });

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Peer One" }))
      .toHaveAttribute("href", "/objects/TestPeer/peer-1");
    await expect
      .element(component.getByRole("link", { name: "Ops Team" }))
      .toHaveAttribute("href", "/objects/CoreAccount/account-1");
  });

  it("marks a source that is a Profile with the Profile icon", async () => {
    // WHEN
    const component = await openPopover({
      ...emptyMetadata,
      source: { id: "profile-1", display_label: "Edge profile", __typename: "ProfileTestPeer" },
    });

    // THEN
    const sourceLink = component.getByRole("link", { name: "Edge profile" });
    await expect.element(sourceLink).toBeVisible();
    expect(
      sourceLink.element().querySelector('iconify-icon[icon="mdi:shape-plus-outline"]')
    ).not.toBeNull();
  });

  it("marks a source that is a Template with the Template icon", async () => {
    // WHEN
    const component = await openPopover({
      ...emptyMetadata,
      source: { id: "template-1", display_label: "Edge template", __typename: "TemplateTestPeer" },
    });

    // THEN
    const sourceLink = component.getByRole("link", { name: "Edge template" });
    await expect.element(sourceLink).toBeVisible();
    expect(sourceLink.element().querySelector("svg.lucide-file-box")).not.toBeNull();
  });

  it("shows the title and the action of the field in its header", async () => {
    // GIVEN
    const component = await render(
      <FieldMetadataPopover
        metadata={emptyMetadata}
        title="Name"
        action={<button type="button">Rename</button>}
      />
    );

    // WHEN
    await component.getByRole("button", { name: "View metadata" }).click();

    // THEN
    await expect.element(component.getByText("Name", { exact: true })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Rename" })).toBeVisible();
  });

  it("shows that a protected field is protected", async () => {
    // WHEN
    const component = await openPopover({ ...emptyMetadata, is_protected: true });

    // THEN
    await expect.element(component.getByText("True")).toBeVisible();
  });
});
