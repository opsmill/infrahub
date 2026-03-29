import { describe, expect, it, vi } from "vitest";

import { render } from "../../../../../../tests/components/render";
import { generatePermission } from "../../../../../../tests/fake/permission";
import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import { ObjectDetailsHeader } from "./object-details-header";

const mockCopyToClipboard = vi.fn();

vi.mock("@/shared/hooks/useCopyToClipboard", () => ({
  useCopyToClipboard: vi.fn(() => ({
    isCopied: false,
    copyToClipboard: mockCopyToClipboard,
  })),
}));

vi.mock("@/entities/nodes/object/ui/queries/get-object.query", () => ({
  useGetObject: vi.fn(() => ({
    data: {
      id: "test-id-123",
      __typename: "InfraDevice",
      display_label: "atl1-core1",
      hfid: ["atl1-core1"],
    },
    isPending: false,
    error: null,
  })),
}));

vi.mock("@/entities/nodes/object/utils/get-node-label", () => ({
  getNodeLabel: vi.fn(() => "atl1-core1"),
}));

const defaultProps = {
  objectSchema: generateNodeSchema({ kind: "InfraDevice" }),
  objectId: "test-id-123",
  permission: generatePermission(),
};

describe("ObjectDetailsHeader", () => {
  it("renders the node display name in the header", async () => {
    // GIVEN
    const component = await render(<ObjectDetailsHeader {...defaultProps} />);

    // THEN
    await expect.element(component.getByRole("heading", { name: "atl1-core1" })).toBeVisible();
  });

  it("renders a copy button next to the node name", async () => {
    // GIVEN
    const component = await render(<ObjectDetailsHeader {...defaultProps} />);

    // THEN
    const header = component.getByTestId("object-header");
    const buttons = header.element().querySelectorAll("button");
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  it("copies the node display name when the copy button is clicked", async () => {
    // GIVEN
    mockCopyToClipboard.mockClear();
    const component = await render(<ObjectDetailsHeader {...defaultProps} />);

    // WHEN
    const header = component.getByTestId("object-header");
    const firstButton = header.element().querySelector("button");
    expect(firstButton).not.toBeNull();
    firstButton!.click();

    // THEN
    expect(mockCopyToClipboard).toHaveBeenCalledWith("atl1-core1");
  });

  it("renders skeleton placeholders while loading", async () => {
    // GIVEN
    const { useGetObject } = await import("@/entities/nodes/object/ui/queries/get-object.query");
    vi.mocked(useGetObject).mockReturnValue({
      data: undefined,
      isPending: true,
      error: null,
    } as ReturnType<typeof useGetObject>);

    const component = await render(<ObjectDetailsHeader {...defaultProps} />);

    // THEN
    expect(component.getByRole("heading", { name: "atl1-core1" }).query()).toBeNull();
    expect(
      component.getByTestId("object-header").element().querySelectorAll("[class*=skeleton]")
    ).not.toHaveLength(0);
  });

  it("renders nothing when there is an error", async () => {
    // GIVEN
    const { useGetObject } = await import("@/entities/nodes/object/ui/queries/get-object.query");
    vi.mocked(useGetObject).mockReturnValue({
      data: undefined,
      isPending: false,
      error: new Error("fetch failed"),
    } as ReturnType<typeof useGetObject>);

    const component = await render(<ObjectDetailsHeader {...defaultProps} />);

    // THEN
    expect(component.getByRole("heading", { name: "atl1-core1" }).query()).toBeNull();
    expect(component.getByTestId("object-header").query()).toBeNull();
  });
});
