import { permissionsAllow } from "./permissions";

export const taskMocksSchema = [
  {
    id: "8a4e2579-c300-48e1-b703-022bf6d224df",
    name: "Task",
    namespace: "Test",
    description: "Issue tracker",
    default_filter: "name__value",
    order_by: ["name__value"],
    display_labels: ["name__value"],
    attributes: [
      {
        id: "30d6f53c-7c97-473e-b0cb-b8f1e1d02f2e",
        name: "name",
        kind: "Text",
        namespace: "Attribute",
        label: "Name",
        description: null,
        default_value: null,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: true,
        branch: true,
        optional: false,
        order_weight: 1000,
      },
      {
        id: "ad1a60f6-efce-445b-9995-b760a6f73f8c",
        name: "description",
        kind: "TextArea",
        namespace: "Attribute",
        label: "Description",
        description: null,
        default_value: null,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: false,
        branch: true,
        optional: true,
        order_weight: 2000,
      },
      {
        id: "374125ad-4bfe-49ac-b6d2-059b7bba19ce",
        name: "completed",
        kind: "Boolean",
        namespace: "Attribute",
        label: "Completed",
        description: null,
        default_value: false,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: false,
        branch: true,
        optional: false,
        order_weight: 3000,
      },
    ],
    relationships: [
      {
        id: "60872203-876d-4ac2-82fe-ff31394f0578",
        name: "member_of_groups",
        peer: "CoreGroup",
        kind: "Group",
        label: "Member Of Groups",
        description: null,
        identifier: "group_member",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [
          { name: "id", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "label__value", kind: "Text", enum: null, object_kind: null, description: null },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 4000,
      },
      {
        id: "1e8d92b9-e101-4445-9b47-92fa17d5f15d",
        name: "subscriber_of_groups",
        peer: "CoreGroup",
        kind: "Group",
        label: "Subscriber Of Groups",
        description: null,
        identifier: "group_subscriber",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [
          { name: "id", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "label__value", kind: "Text", enum: null, object_kind: null, description: null },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 5000,
      },
    ],
    label: "Task",
    inherit_from: [],
    groups: [],
    branch: true,
    filters: [
      { name: "ids", kind: "Text", enum: null, object_kind: null, description: null },
      { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
      {
        name: "completed__value",
        kind: "Boolean",
        enum: null,
        object_kind: null,
        description: null,
      },
    ],
    kind: "TestTask",
  },
];

export const taskMocksQuery = `
query TestTask {
  TestTask(offset: 0,limit: 10) {
    count
    edges {
      node {
        id
        display_label
        __typename
        name {
            value
        }
        description {
            value
        }
        completed {
            value
        }
      }
    }
    permissions {
      edges {
        node {
          kind
          view
          create
          update
          delete
        }
      }
    }
  }
}
`;

export const taskMocksData = {
  TestTask: {
    count: 1,
    edges: [
      {
        node: {
          id: "c5b3043d-bb86-46ac-8790-227a61de3305",
          display_label: "aze",
          __typename: "TestTask",
          name: { value: "aze", __typename: "TextAttribute" },
          description: { value: null, __typename: "TextAttribute" },
          completed: { value: false, __typename: "CheckboxAttribute" },
        },
        __typename: "EdgedTestTask",
      },
    ],
    permissions: permissionsAllow,
    __typename: "PaginatedTestTask",
  },
};
