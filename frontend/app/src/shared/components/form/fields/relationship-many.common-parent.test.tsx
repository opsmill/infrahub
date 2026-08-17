import { afterEach, describe, expect, test, vi } from "vitest";

import { TestForm } from "../../../../../tests/components/form.story";
import { render } from "../../../../../tests/components/render";
import { generateRelationshipSchema } from "../../../../../tests/fake/schema";
import RelationshipManyField from "./relationships/relationship-many.field";

// Capture the props handed to the input so we can assert the common_parent wiring
// without driving the whole combobox/query stack.
let lastFilterQuery: unknown;
let lastAddNewInitialObject: unknown;
let lastEnforceOnIdSearch: unknown;
vi.mock("@/shared/components/inputs/relationship-many", () => ({
  RelationshipManyInput: (props: {
    filterQuery?: unknown;
    addNewInitialObject?: unknown;
    enforceFilterQueryOnIdSearch?: unknown;
  }) => {
    lastFilterQuery = props.filterQuery;
    lastAddNewInitialObject = props.addNewInitialObject;
    lastEnforceOnIdSearch = props.enforceFilterQueryOnIdSearch;
    return <input data-testid="many-input" />;
  },
}));

describe("RelationshipManyField - common_parent filtering", () => {
  afterEach(() => {
    lastFilterQuery = undefined;
    lastAddNewInitialObject = undefined;
    lastEnforceOnIdSearch = undefined;
    vi.clearAllMocks();
  });

  test("filters the peer options by the common_parent chosen in a sibling field", async () => {
    // GIVEN a relationship declaring common_parent: device, with the sibling device picked
    const relationship = generateRelationshipSchema({
      name: "profile_one",
      peer: "TestProfile",
      common_parent: "device",
    });
    const deviceValue = {
      source: { type: "user" as const },
      value: { id: "dev-1", display_label: "dc1-device", __typename: "TestDevice" },
    };

    // WHEN the field renders with that sibling value seeded into the form
    await render(
      <TestForm defaultValues={{ device: deviceValue }}>
        <RelationshipManyField
          type="relationship"
          name="profile_one"
          label="Profile One"
          peer="TestProfile"
          relationship={relationship}
        />
      </TestForm>
    );

    // THEN the input receives a single-hop filter on the chosen parent; the UUID-search override
    // is closed, and "Add new" is pre-filled with that parent so a created peer stays valid.
    await expect.poll(() => lastFilterQuery).toEqual({ device__ids: ["dev-1"] });
    expect(lastEnforceOnIdSearch).toBe(true);
    expect(lastAddNewInitialObject).toEqual({
      device: { node: { id: "dev-1", display_label: "dc1-device", __typename: "TestDevice" } },
    });
  });

  test("passes no filter when the sibling common_parent field is empty", async () => {
    const relationship = generateRelationshipSchema({
      name: "profile_one",
      peer: "TestProfile",
      common_parent: "device",
    });

    await render(
      <TestForm>
        <RelationshipManyField
          type="relationship"
          name="profile_one"
          label="Profile One"
          peer="TestProfile"
          relationship={relationship}
        />
      </TestForm>
    );

    await expect.poll(() => lastFilterQuery).toBeUndefined();
  });

  test("passes no filter when the schema declares no common_parent", async () => {
    const relationship = generateRelationshipSchema({ name: "tags", peer: "TestProfile" });

    await render(
      <TestForm>
        <RelationshipManyField
          type="relationship"
          name="tags"
          label="Tags"
          peer="TestProfile"
          relationship={relationship}
        />
      </TestForm>
    );

    await expect.poll(() => lastFilterQuery).toBeUndefined();
  });
});
