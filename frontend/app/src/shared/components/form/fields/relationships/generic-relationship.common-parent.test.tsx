import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { TestForm } from "../../../../../../tests/components/form.story";
import { render } from "../../../../../../tests/components/render";
import {
  generateGenericSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { GenericRelationshipField } from "./generic-relationship.field";

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

// A generic peer with a single concrete implementation (auto-selected). The concrete kind has a
// Parent relationship named "device", so the manual picker would show by default.
const concretePeer = generateNodeSchema({
  kind: "TestProfileOne",
  name: "ProfileOne",
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

const genericPeer = generateGenericSchema({
  kind: "TestGenericProfile",
  name: "GenericProfile",
  relationships: [],
  used_by: ["TestProfileOne"],
});

const deviceValue = {
  source: { type: "user" as const },
  value: { id: "dev-1", display_label: "dc1-device", __typename: "TestDevice" },
};

describe("GenericRelationshipField - common_parent", () => {
  beforeEach(() => {
    store.set(nodeSchemasAtom, [concretePeer]);
    store.set(genericSchemasAtom, [genericPeer]);
  });
  afterEach(() => {
    lastParent = undefined;
    lastAddNewInitialObject = undefined;
    vi.clearAllMocks();
  });

  test("hides the manual parent picker and filters by the sibling when common_parent is set", async () => {
    const relationship = generateRelationshipSchema({
      name: "profile_one",
      peer: "TestGenericProfile",
      cardinality: "one",
      common_parent: "device",
    });

    await render(
      <TestForm defaultValues={{ device: deviceValue }}>
        <GenericRelationshipField
          type="relationship"
          name="profile_one"
          label="Profile One"
          peer="TestGenericProfile"
          relationship={relationship}
        />
      </TestForm>
    );

    await expect.poll(() => lastParent).toEqual({ name: "device", value: "dev-1" });
    expect(document.querySelectorAll('[data-testid="rel-input"]')).toHaveLength(1);
    expect(lastAddNewInitialObject).toEqual({
      device: { node: { id: "dev-1", display_label: "dc1-device", __typename: "TestDevice" } },
    });
  });

  test("shows the manual parent picker when common_parent is not set", async () => {
    const relationship = generateRelationshipSchema({
      name: "profile_one",
      peer: "TestGenericProfile",
      cardinality: "one",
    });

    await render(
      <TestForm>
        <GenericRelationshipField
          type="relationship"
          name="profile_one"
          label="Profile One"
          peer="TestGenericProfile"
          relationship={relationship}
        />
      </TestForm>
    );

    // Manual parent picker present in addition to the peer picker → two inputs.
    await expect.poll(() => document.querySelectorAll('[data-testid="rel-input"]').length).toBe(2);
  });
});
