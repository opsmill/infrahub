import { beforeEach, describe, expect, it, vi } from "vitest";

import { store } from "@/shared/stores";

import type { NodeMetadata } from "@/entities/nodes/types";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import { NodeMetadata as NodeMetadataComponent } from "./node-metadata-popover";

vi.mock("@/entities/nodes/object/ui/queries/get-node-metadata.query", () => ({
  useGetNodeMetadata: vi.fn(),
}));

import { useGetNodeMetadata } from "@/entities/nodes/object/ui/queries/get-node-metadata.query";

describe("NodeMetadata", () => {
  const coreAccountSchema = generateNodeSchema({
    kind: "CoreAccount",
    name: "Account",
    namespace: "Core",
    label: "Account",
    display_labels: ["name__value"],
  });

  beforeEach(() => {
    store.set(nodeSchemasAtom, [coreAccountSchema]);
  });

  const mockMetadata: NodeMetadata = {
    created_at: "2024-01-15T10:30:00Z",
    created_by: {
      id: "user-1",
      display_label: "John Doe",
      __typename: "CoreAccount",
      hfid: ["john-doe"],
    },
    updated_at: "2024-01-16T14:20:00Z",
    updated_by: {
      id: "user-2",
      display_label: "Jane Smith",
      __typename: "CoreAccount",
      hfid: ["jane-smith"],
    },
  };

  it("displays loading state while fetching metadata", async () => {
    // GIVEN
    vi.mocked(useGetNodeMetadata).mockReturnValue({
      data: undefined,
      isPending: true,
      error: null,
    } as any);

    // WHEN
    const component = await render(
      <NodeMetadataComponent objectKind="InfraDevice" objectId="test-id" />
    );

    // THEN
    await expect.element(component.getByText("Loading...").first()).toBeVisible();
  });

  it("displays error message when fetch fails", async () => {
    // GIVEN
    const errorMessage = "Failed to fetch metadata";
    vi.mocked(useGetNodeMetadata).mockReturnValue({
      data: undefined,
      isPending: false,
      error: new Error(errorMessage),
    } as any);

    // WHEN
    const component = await render(
      <NodeMetadataComponent objectKind="InfraDevice" objectId="test-id" />
    );

    // THEN
    await expect.element(component.getByText(errorMessage)).toBeVisible();
  });

  it("displays error message when no data is returned", async () => {
    // GIVEN
    vi.mocked(useGetNodeMetadata).mockReturnValue({
      data: undefined,
      isPending: false,
      error: null,
    } as any);

    // WHEN
    const component = await render(
      <NodeMetadataComponent objectKind="InfraDevice" objectId="test-id" />
    );

    // THEN
    await expect.element(component.getByText("No metadata available")).toBeVisible();
  });

  it("displays metadata fields with values", async () => {
    // GIVEN
    vi.mocked(useGetNodeMetadata).mockReturnValue({
      data: mockMetadata,
      isPending: false,
      error: null,
    } as any);

    // WHEN
    const component = await render(
      <NodeMetadataComponent objectKind="InfraDevice" objectId="test-id" />
    );

    // THEN
    await expect.element(component.getByText("Created at")).toBeVisible();
    await expect.element(component.getByText("Created by")).toBeVisible();
    await expect.element(component.getByText("Updated at")).toBeVisible();
    await expect.element(component.getByText("Updated by")).toBeVisible();

    // Verify user links are displayed with their display labels
    await expect.element(component.getByText("John Doe")).toBeVisible();
    await expect.element(component.getByText("Jane Smith")).toBeVisible();
  });

  it("displays metadata when created_by is null", async () => {
    // GIVEN
    const metadataWithoutCreatedBy: NodeMetadata = {
      ...mockMetadata,
      created_by: null,
    };
    vi.mocked(useGetNodeMetadata).mockReturnValue({
      data: metadataWithoutCreatedBy,
      isPending: false,
      error: null,
    } as any);

    // WHEN
    const component = await render(
      <NodeMetadataComponent objectKind="InfraDevice" objectId="test-id" />
    );

    // THEN
    await expect.element(component.getByText("Created by")).toBeVisible();
    await expect.element(component.getByText("Created at")).toBeVisible();
    // Verify updated_by user link is displayed
    await expect.element(component.getByRole("link", { name: "Jane Smith" })).toBeVisible();
  });

  it("displays metadata when updated_by is null", async () => {
    // GIVEN
    const metadataWithoutUpdatedBy: NodeMetadata = {
      ...mockMetadata,
      updated_by: null,
    };
    vi.mocked(useGetNodeMetadata).mockReturnValue({
      data: metadataWithoutUpdatedBy,
      isPending: false,
      error: null,
    } as any);

    // WHEN
    const component = await render(
      <NodeMetadataComponent objectKind="InfraDevice" objectId="test-id" />
    );

    // THEN
    await expect.element(component.getByText("Updated by")).toBeVisible();
    await expect.element(component.getByText("Updated at")).toBeVisible();
    // Verify created_by user link is displayed
    await expect.element(component.getByRole("link", { name: "John Doe" })).toBeVisible();
  });

  it("renders user links with correct URLs", async () => {
    // GIVEN
    vi.mocked(useGetNodeMetadata).mockReturnValue({
      data: mockMetadata,
      isPending: false,
      error: null,
    } as any);

    // WHEN
    const component = await render(
      <NodeMetadataComponent objectKind="InfraDevice" objectId="test-id" />
    );

    // THEN
    const createdByLink = component.getByRole("link", { name: "John Doe" });
    await expect.element(createdByLink).toBeVisible();
    await expect.element(createdByLink).toHaveAttribute("href", "/objects/CoreAccount/user-1");

    const updatedByLink = component.getByRole("link", { name: "Jane Smith" });
    await expect.element(updatedByLink).toBeVisible();
    await expect.element(updatedByLink).toHaveAttribute("href", "/objects/CoreAccount/user-2");
  });

  it("displays system user when id is __system__", async () => {
    // GIVEN
    const metadataWithSystemUser: NodeMetadata = {
      created_at: "2024-01-15T10:30:00Z",
      created_by: {
        id: "__system__",
        display_label: "System",
        __typename: "[Infrahub System]",
        hfid: ["__system__"],
      },
      updated_at: "2024-01-16T14:20:00Z",
      updated_by: {
        id: "__system__",
        display_label: "[Infrahub System]",
        __typename: "CoreAccount",
        hfid: ["__system__"],
      },
    };
    vi.mocked(useGetNodeMetadata).mockReturnValue({
      data: metadataWithSystemUser,
      isPending: false,
      error: null,
    } as any);

    // WHEN
    const component = await render(
      <NodeMetadataComponent objectKind="InfraDevice" objectId="test-id" />
    );

    // THEN
    await expect.element(component.getByText("Created by")).toBeVisible();
    await expect.element(component.getByText("Updated by")).toBeVisible();

    // Verify system user links are displayed
    const systemLabel = component.getByText("[Infrahub System]");
    await expect.element(systemLabel).toBeVisible();
    await expect.element(systemLabel).not.toHaveAttribute("href");
  });
});
