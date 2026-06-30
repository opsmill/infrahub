import { describe, expect, test, vi } from "vitest";

import type { NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

import { render } from "../../../../../../tests/components/render";
import { ObjectDetails } from "./object-details";

// The real cards pull in schema/query machinery that is out of scope here; we only
// assert the layout (left column, ordering, slot placement), so stub each card with
// a sentinel.
vi.mock("./object-details-card", () => ({
  ObjectDetailsCard: () => <div data-testid="object-details-card">details</div>,
}));
vi.mock("./object-profiles-groups-card", () => ({
  ObjectProfilesGroupsCard: () => <div data-testid="profiles-groups-card">groups</div>,
}));
vi.mock("./object-activities-card", () => ({
  ObjectActivitiesCard: () => <div data-testid="activities-card">activities</div>,
}));
vi.mock("./file-preview-card", () => ({
  FilePreviewCard: () => <div data-testid="file-preview-card">file</div>,
}));
vi.mock("@/shared/hooks/useTitle", () => ({ useTitle: () => {} }));

const objectSchema = { kind: "CoreGenericAccount" } as unknown as ModelSchema;
const objectData = {
  id: "1",
  __typename: "CoreGenericAccount",
} as unknown as NodeObjectWithMetadata;
const permission = {} as Permission;

describe("ObjectDetails", () => {
  test("renders the standard cards without a left-column extra by default", async () => {
    const component = await render(
      <ObjectDetails objectSchema={objectSchema} objectData={objectData} permission={permission} />
    );

    await expect.element(component.getByTestId("object-details-card")).toBeVisible();
    await expect.element(component.getByTestId("profiles-groups-card")).toBeVisible();
    await expect.element(component.getByTestId("activities-card")).toBeVisible();
    // No FILE_OBJECT_KIND schema and no slot content → neither extra renders.
    expect(component.getByTestId("file-preview-card").elements()).toHaveLength(0);
    expect(component.getByTestId("left-column-extra").elements()).toHaveLength(0);
  });

  test("renders leftColumnExtra inside the left column, after the details card", async () => {
    const component = await render(
      <ObjectDetails
        objectSchema={objectSchema}
        objectData={objectData}
        permission={permission}
        leftColumnExtra={<div data-testid="left-column-extra">extra</div>}
      />
    );

    const detailsCard = component.getByTestId("object-details-card").element() as HTMLElement;
    const extra = component.getByTestId("left-column-extra").element() as HTMLElement;
    const groupsCard = component.getByTestId("profiles-groups-card").element() as HTMLElement;

    await expect.element(component.getByTestId("left-column-extra")).toBeVisible();

    // The extra lives in the SAME column container as the details card (the left
    // <Col>), and the groups card sits in a different column.
    const leftColumn = detailsCard.parentElement as HTMLElement;
    expect(leftColumn.contains(extra)).toBe(true);
    expect(leftColumn.contains(groupsCard)).toBe(false);

    // The extra comes AFTER the details card in document order (both direct
    // children of the left column).
    const children = Array.from(leftColumn.children);
    const detailsIndex = children.findIndex((child) => child.contains(detailsCard));
    const extraIndex = children.findIndex((child) => child.contains(extra));
    expect(detailsIndex).toBeGreaterThanOrEqual(0);
    expect(extraIndex).toBeGreaterThan(detailsIndex);
  });
});
