import { afterEach, describe, expect, test, vi } from "vitest";

import { TestForm } from "../../../../../../tests/components/form.story";
import { render } from "../../../../../../tests/components/render";
import { generateRelationshipSchema } from "../../../../../../tests/fake/schema";
import RelationshipHierarchicalField from "./relationship-hierarchical.field";

// Capture the props handed to the hierarchical inputs.
let lastFilterQuery: unknown;
let lastHideExplore: unknown;
vi.mock("@/entities/nodes/relationships/ui/relationship-hierarchical-input", () => ({
  RelationshipHierarchicalInput: (props: { filterQuery?: unknown; hideExplore?: unknown }) => {
    lastFilterQuery = props.filterQuery;
    lastHideExplore = props.hideExplore;
    return <input data-testid="hierarchical-input" />;
  },
  RelationshipHierarchicalManyInput: (props: { filterQuery?: unknown; hideExplore?: unknown }) => {
    lastFilterQuery = props.filterQuery;
    lastHideExplore = props.hideExplore;
    return <input data-testid="hierarchical-input" />;
  },
}));

const deviceValue = {
  source: { type: "user" as const },
  value: { id: "dev-1", display_label: "dc1-device", __typename: "TestDevice" },
};

describe("RelationshipHierarchicalField - common_parent", () => {
  afterEach(() => {
    lastFilterQuery = undefined;
    lastHideExplore = undefined;
    vi.clearAllMocks();
  });

  test("filters by the sibling common_parent value", async () => {
    const relationship = generateRelationshipSchema({
      name: "children",
      peer: "TestNode",
      cardinality: "one",
      hierarchical: "TestNode",
      common_parent: "device",
    });

    await render(
      <TestForm defaultValues={{ device: deviceValue }}>
        <RelationshipHierarchicalField
          name="children"
          label="Children"
          peer="TestNode"
          relationship={relationship}
        />
      </TestForm>
    );

    await expect.poll(() => lastFilterQuery).toEqual({ device__ids: ["dev-1"] });
    // The tree explorer can't honor the filter, so it is dropped when common_parent applies.
    expect(lastHideExplore).toBe(true);
  });

  test("passes no filter when the schema declares no common_parent", async () => {
    const relationship = generateRelationshipSchema({
      name: "children",
      peer: "TestNode",
      cardinality: "one",
      hierarchical: "TestNode",
    });

    await render(
      <TestForm>
        <RelationshipHierarchicalField
          name="children"
          label="Children"
          peer="TestNode"
          relationship={relationship}
        />
      </TestForm>
    );

    await expect.poll(() => lastFilterQuery).toBeUndefined();
    expect(lastHideExplore).toBe(false);
  });
});
