import { afterEach, describe, expect, it, vi } from "vitest";

import { store } from "@/shared/stores";

import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../tests/components/render";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { IpPoolExtraFieldsLine } from "./ip-pool-extra-fields";

vi.mock("@/entities/nodes/object/ui/queries/get-object.query", () => ({
  useGetObject: vi.fn(),
}));

const coreAttributes = [
  generateAttributeSchema({ name: "name" }),
  generateAttributeSchema({ name: "default_prefix_length", kind: "Number" }),
];

const extendedSchema = generateNodeSchema({
  kind: "CoreIPPrefixPool",
  attributes: [...coreAttributes, generateAttributeSchema({ name: "contact", label: "Contact" })],
  relationships: [
    generateRelationshipSchema({
      name: "site",
      label: "Site",
      peer: "LocationSite",
      kind: "Attribute",
      cardinality: "one",
    }),
  ],
});

const initialNodeSchemas = store.get(nodeSchemasAtom);

describe("IpPoolExtraFieldsLine", () => {
  afterEach(() => {
    vi.resetAllMocks();
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  it("shows nothing and reads nothing when the pool schema has no extra field", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      kind: "CoreIPPrefixPool",
      attributes: coreAttributes,
      relationships: [],
    });

    // WHEN
    const component = await render(<IpPoolExtraFieldsLine poolId="pool-id" schema={schema} />);

    // THEN
    await expect.element(component.getByRole("definition")).not.toBeInTheDocument();
    expect(useGetObject).not.toHaveBeenCalled();
  });

  it("shows the extra attributes and relationships of an extended pool schema", async () => {
    // GIVEN
    store.set(nodeSchemasAtom, [
      generateNodeSchema({ kind: "LocationSite", display_label: "name__value" }),
    ]);
    vi.mocked(useGetObject).mockReturnValue({
      data: {
        id: "pool-id",
        __typename: "CoreIPPrefixPool",
        contact: { value: "noc@example.com" },
        site: { node: { id: "site-id", __typename: "LocationSite", display_label: "PAR1" } },
      },
      isPending: false,
      error: null,
    } as unknown as ReturnType<typeof useGetObject>);

    // WHEN
    const component = await render(
      <IpPoolExtraFieldsLine poolId="pool-id" schema={extendedSchema} />
    );

    // THEN
    await expect.element(component.getByRole("term").first()).toHaveTextContent("Contact");
    await expect
      .element(component.getByRole("definition").first())
      .toHaveTextContent("noc@example.com");
    await expect.element(component.getByRole("link", { name: "PAR1" })).toBeVisible();
    expect(vi.mocked(useGetObject).mock.calls[0]?.[0].getAttributesVisible?.([])).toEqual([
      expect.objectContaining({ name: "contact" }),
    ]);
  });

  it("leaves the header as it is when the extra fields cannot be read", async () => {
    // GIVEN
    vi.mocked(useGetObject).mockReturnValue({
      data: undefined,
      isPending: false,
      error: new Error("Unavailable"),
    } as unknown as ReturnType<typeof useGetObject>);

    // WHEN
    const component = await render(
      <IpPoolExtraFieldsLine poolId="pool-id" schema={extendedSchema} />
    );

    // THEN
    await expect.element(component.getByText("Contact")).not.toBeInTheDocument();
  });
});
