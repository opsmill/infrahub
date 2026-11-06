import { describe, expect, test, vi } from "vitest";

import { CoreFileForm } from "@/shared/components/form/core-file-form";

import { render } from "../../../../tests/components/render";
import {
  generateAttributeSchema,
  generateContainerSchema,
  generateNodeSchema,
} from "../../../../tests/fake/schema";

vi.mock("@/entities/resource-manager/ui/queries/get-number-pools.query", () => ({
  useGetNumberPools: () => ({ data: [], isPending: false }),
}));

describe("CoreFileForm", () => {
  test("renders one panel per container of the kind", async () => {
    const schema = generateNodeSchema({
      kind: "TestContract",
      inherit_from: ["CoreFileObject"],
      containers: [generateContainerSchema({ name: "legal", label: "Legal" })],
      attributes: [
        generateAttributeSchema({ name: "name", label: "Name" }),
        generateAttributeSchema({ name: "signatory", label: "Signatory", container: "legal" }),
      ],
      relationships: [],
    });

    const component = await render(<CoreFileForm schema={schema} />);

    await expect
      .element(component.getByRole("region", { name: "Legal" }).getByLabelText("Signatory"))
      .toBeVisible();
    await expect
      .element(component.getByRole("region", { name: "Details" }).getByLabelText("Name"))
      .toBeVisible();
  });
});
