import { describe, expect, test, vi } from "vitest";

import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import {
  GENERIC_REPOSITORY_KIND,
  READONLY_REPOSITORY_KIND,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";

import { render } from "../../../../../../tests/components/render";
import { generatePermission } from "../../../../../../tests/fake/permission";
import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import { ObjectDetails } from "./object-details";

vi.mock("@/entities/nodes/object/ui/object-details/object-details-card", () => ({
  ObjectDetailsCard: () => null,
}));
vi.mock("@/entities/nodes/object/ui/object-details/object-profiles-groups-card", () => ({
  ObjectProfilesGroupsCard: () => null,
}));
vi.mock("@/entities/nodes/object/ui/object-details/object-activities-card", () => ({
  ObjectActivitiesCard: () => null,
}));
vi.mock("@/entities/repository/ui/repository-delivery-section", () => ({
  RepositoryDeliverySection: () => <p>Push to remote</p>,
}));

const renderDetails = (kind: string) => {
  const [namespace, name] = [kind.slice(0, 4), kind.slice(4)];
  const objectSchema = generateNodeSchema({
    kind,
    namespace,
    name,
    inherit_from: [GENERIC_REPOSITORY_KIND],
  });
  const objectData: NodeObjectWithMetadata = {
    id: "repo-1",
    display_label: "repo-a",
    __typename: kind,
  };

  return render(
    <ObjectDetails
      objectSchema={objectSchema}
      objectData={objectData}
      permission={generatePermission()}
    />
  );
};

describe("ObjectDetails", () => {
  test("shows the push section on a repository", async () => {
    // WHEN
    const component = await renderDetails(REPOSITORY_KIND);

    // THEN
    await expect.element(component.getByText("Push to remote")).toBeVisible();
  });

  test("never shows the push section on a read-only repository", async () => {
    // WHEN
    const component = await renderDetails(READONLY_REPOSITORY_KIND);

    // THEN
    await expect.element(component.getByText("Push to remote")).not.toBeInTheDocument();
  });
});
