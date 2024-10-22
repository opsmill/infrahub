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
        id: "374125ad-4bfe-49ac-b6d2-059b7bba19ce",
        name: "completed",
        kind: "Boolean",
        namespace: "Attribute",
        label: "Completed",
        description: null,
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
    relationships: [],
    label: "Task",
    inherit_from: [],
    groups: [],
    branch: true,
    filters: [],
    kind: "TestTask",
  },
];

export const taskMocksSchemaWithDefaultValue = [
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
    relationships: [],
    label: "Task",
    inherit_from: [],
    groups: [],
    branch: true,
    filters: [],
    kind: "TestTask",
  },
];

export const taskMocksSchemaOptional = [
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
        optional: true,
        order_weight: 3000,
      },
    ],
    relationships: [],
    label: "Task",
    inherit_from: [],
    groups: [],
    branch: true,
    filters: [],
    kind: "TestTask",
  },
];

export const taskMocksQuery = `
query TestTask($offset: Int, $limit: Int) {
  TestTask(offset: $offset,limit: $limit) {
    count
    edges {
      node {
        id
        display_label
        __typename
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
    count: 0,
    edges: [],
    permissions: permissionsAllow,
    __typename: "PaginatedTestTask",
  },
};
