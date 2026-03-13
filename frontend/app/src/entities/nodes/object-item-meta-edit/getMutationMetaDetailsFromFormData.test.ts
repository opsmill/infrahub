import { describe, expect, it } from "vitest";

import getMutationMetaDetailsFromFormData from "@/entities/nodes/object-item-meta-edit/getMutationMetaDetailsFromFormData";

import { generateNodeSchema } from "../../../../tests/fake/schema";

const nodeSchema = generateNodeSchema();

const nodeData = {
  id: "node-id",
  hfid: ["atl1-edge1"],
  display_label: "atl1-edge1",
  name: {
    value: "atl1-edge1",
    updated_at: "2023-07-10T15:01:29.806543+00:00",
    is_protected: true,
    source: {
      id: "bf26a7e3-db46-40f3-b02b-40c6ef362d13",
      display_label: "Pop-Builder",
      __typename: "CoreAccount",
    },
    owner: null,
    __typename: "TextAttribute",
  },
  description: {
    value: null,
    updated_at: "2023-07-10T15:01:29.806543+00:00",
    is_protected: false,
    source: null,
    owner: null,
    __typename: "TextAttribute",
  },
  type: {
    value: "7280R3",
    updated_at: "2023-07-10T15:01:29.806543+00:00",
    is_protected: false,
    source: {
      id: "bf26a7e3-db46-40f3-b02b-40c6ef362d13",
      display_label: "Pop-Builder",
      __typename: "CoreAccount",
    },
    owner: null,
    __typename: "TextAttribute",
  },
  site: {
    node: {
      id: "side-id",
      display_label: "atl1",
      __typename: "BuiltinLocation",
    },
    properties: {
      updated_at: "2023-07-10T15:01:29.806543+00:00",
      is_protected: true,
      source: {
        id: "bf26a7e3-db46-40f3-b02b-40c6ef362d13",
        display_label: "Pop-Builder",
        __typename: "CoreAccount",
      },
      owner: null,
      __typename: "RelationshipProperty",
    },
    __typename: "NestedEdgedBuiltinLocation",
  },
  status: {
    node: {
      id: "6c96efcf-acec-449c-9a8f-b3b069c94e76",
      display_label: "Active",
      __typename: "BuiltinStatus",
    },
    properties: {
      updated_at: "2023-07-10T15:01:29.806543+00:00",
      is_protected: null,
      source: null,
      owner: {
        id: "9622f4c6-2a61-4e71-8d78-36dcab0d219c",
        display_label: "Operation Team",
        __typename: "CoreAccount",
      },
      __typename: "RelationshipProperty",
    },
    __typename: "NestedEdgedBuiltinStatus",
  },
  role: {
    node: {
      id: "4ad3a31b-6446-4149-8498-da531776fc5f",
      display_label: "Edge",
      __typename: "BuiltinRole",
    },
    properties: {
      updated_at: "2023-07-10T15:01:29.806543+00:00",
      is_protected: true,
      source: {
        id: "bf26a7e3-db46-40f3-b02b-40c6ef362d13",
        display_label: "Pop-Builder",
        __typename: "CoreAccount",
      },
      owner: {
        id: "0552d2d5-e38f-414b-8891-a718c1fa0657",
        display_label: "Engineering Team",
        __typename: "CoreAccount",
      },
      __typename: "RelationshipProperty",
    },
    __typename: "NestedEdgedBuiltinRole",
  },
  asn: {
    node: {
      id: "74bb08a5-30fa-4c96-99d9-a9a8f91716e7",
      display_label: "AS64496 64496",
      __typename: "InfraAutonomousSystem",
    },
    properties: {
      updated_at: "2023-07-10T15:01:29.806543+00:00",
      is_protected: true,
      source: {
        id: "bf26a7e3-db46-40f3-b02b-40c6ef362d13",
        display_label: "Pop-Builder",
        __typename: "CoreAccount",
      },
      owner: {
        id: "0552d2d5-e38f-414b-8891-a718c1fa0657",
        display_label: "Engineering Team",
        __typename: "CoreAccount",
      },
      __typename: "RelationshipProperty",
    },
    __typename: "NestedEdgedInfraAutonomousSystem",
  },
  tags: {
    edges: [
      {
        node: {
          id: "134f3f6d-1d53-4b00-8a3d-3e4dce3f2996",
          display_label: "green",
          __typename: "BuiltinTag",
        },
        properties: {
          updated_at: "2023-07-10T15:01:29.806543+00:00",
          is_protected: null,
          source: null,
          owner: null,
          __typename: "RelationshipProperty",
        },
        __typename: "NestedEdgedBuiltinTag",
      },
      {
        node: {
          id: "25efcc5c-407f-404e-9a77-0161bb9558e8",
          display_label: "red",
          __typename: "BuiltinTag",
        },
        properties: {
          updated_at: "2023-07-10T15:01:29.806543+00:00",
          is_protected: null,
          source: null,
          owner: null,
          __typename: "RelationshipProperty",
        },
        __typename: "NestedEdgedBuiltinTag",
      },
    ],
    __typename: "NestedPaginatedBuiltinTag",
  },
  primary_address: {
    node: {
      id: "034c8cf0-337b-4e0f-9915-2b50d69224ed",
      display_label: "172.20.20.19/24",
      __typename: "InfraIPAddress",
    },
    properties: {
      updated_at: "2023-07-10T15:01:30.985897+00:00",
      is_protected: null,
      source: null,
      owner: null,
      __typename: "RelationshipProperty",
    },
    __typename: "NestedEdgedInfraIPAddress",
  },
  platform: {
    node: {
      id: "a04c3ca4-865a-458c-81c4-51e50205da44",
      display_label: "Arista EOS",
      __typename: "InfraPlatform",
    },
    properties: {
      updated_at: "2023-07-10T15:01:29.806543+00:00",
      is_protected: true,
      source: {
        id: "bf26a7e3-db46-40f3-b02b-40c6ef362d13",
        display_label: "Pop-Builder",
        __typename: "CoreAccount",
      },
      owner: null,
      __typename: "RelationshipProperty",
    },
    __typename: "NestedEdgedInfraPlatform",
  },
  interfaces: { count: 14, __typename: "NestedPaginatedInfraInterface" },
  __typename: "InfraDevice",
};

const newDataForMetaEdit = {
  owner: "owner-id",
  source: "source-id",
  is_protected: true,
};

const updatedObject = getMutationMetaDetailsFromFormData(
  nodeSchema,
  newDataForMetaEdit,
  nodeData,
  "relationship",
  "site",
  nodeData.site.properties
);

describe("Mutation details from object data", () => {
  it("should return a correct updated object structure", () => {
    expect(updatedObject).toStrictEqual({
      id: nodeData.id,
      site: {
        id: nodeData.site.node.id,
        _relation__owner: newDataForMetaEdit.owner,
        _relation__source: newDataForMetaEdit.source,
        _relation__is_protected: newDataForMetaEdit.is_protected,
      },
    });
  });
});
