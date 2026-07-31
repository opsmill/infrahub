import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { TestForm } from "../../../../../../tests/components/form.story";
import { render } from "../../../../../../tests/components/render";
import {
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { NodeRelationshipField } from "./regular-relationship.field";

// Capture the props handed to the peer picker.
let lastParent: unknown;
let lastAddNewInitialObject: unknown;
vi.mock("@/shared/components/inputs/relationship-one", () => ({
  RelationshipInput: (props: { parent?: unknown; addNewInitialObject?: unknown }) => {
    lastParent = props.parent;
    lastAddNewInitialObject = props.addNewInitialObject;
    return <input data-testid="rel-input" />;
  },
}));

// Peer has a Parent relationship named "device", so the manual picker would show by default.
const peerSchema = generateNodeSchema({
  kind: "TestProfile",
  name: "Profile",
  relationships: [
    generateRelationshipSchema({
      name: "device",
      peer: "TestDevice",
      kind: "Parent",
      cardinality: "one",
      optional: false,
    }),
  ],
});

const deviceValue = {
  source: { type: "user" as const },
  value: { id: "dev-1", display_label: "dc1-device", __typename: "TestDevice" },
};

describe("NodeRelationshipField - common_parent", () => {
  beforeEach(() => {
    store.set(nodeSchemasAtom, [peerSchema]);
  });
  afterEach(() => {
    lastParent = undefined;
    lastAddNewInitialObject = undefined;
    vi.clearAllMocks();
  });

  test("hides the manual parent picker and filters by the sibling when common_parent is set", async () => {
    const relationship = generateRelationshipSchema({
      name: "profile_one",
      peer: "TestProfile",
      cardinality: "one",
      common_parent: "device",
    });

    await render(
      <TestForm defaultValues={{ device: deviceValue }}>
        <NodeRelationshipField
          type="relationship"
          name="profile_one"
          label="Profile One"
          peer="TestProfile"
          relationship={relationship}
        />
      </TestForm>
    );

    // Only the peer picker renders (manual parent picker hidden), filtered by the sibling,
    // with "Add new" pre-filled so a created peer stays valid.
    await expect.poll(() => lastParent).toEqual({ name: "device", value: "dev-1" });
    expect(document.querySelectorAll('[data-testid="rel-input"]')).toHaveLength(1);
    expect(lastAddNewInitialObject).toEqual({
      device: { node: { id: "dev-1", display_label: "dc1-device", __typename: "TestDevice" } },
    });
  });

  test("shows the manual parent picker when common_parent is not set", async () => {
    const relationship = generateRelationshipSchema({
      name: "profile_one",
      peer: "TestProfile",
      cardinality: "one",
    });

    await render(
      <TestForm>
        <NodeRelationshipField
          type="relationship"
          name="profile_one"
          label="Profile One"
          peer="TestProfile"
          relationship={relationship}
        />
      </TestForm>
    );

    // Manual parent picker present in addition to the peer picker → two inputs.
    await expect.poll(() => document.querySelectorAll('[data-testid="rel-input"]').length).toBe(2);
  });
});
