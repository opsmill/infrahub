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
        name: "counter",
        kind: "Number",
        namespace: "Attribute",
        label: "Counter",
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
        name: "counter",
        kind: "Number",
        namespace: "Attribute",
        label: "Counter",
        description: null,
        default_value: 5,
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
        name: "counter",
        kind: "Number",
        namespace: "Attribute",
        label: "Counter",
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
query TestTask {
  TestTask(offset: 0,limit: 10) {
    count
    edges {
      node {
        id
        display_label
        __typename
        counter {
            value
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
    __typename: "PaginatedTestTask",
  },
};
