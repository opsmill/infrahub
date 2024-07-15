export const taskMocksSchema = [
  {
    id: "8a4e2579-c300-48e1-b703-022bf6d224df",
    name: "Task",
    namespace: "Test",
    description: "Issue tracker",
    default_filter: "name__value",
    order_by: ["name__value"],
    display_labels: ["name__value"],
    attributes: [],
    relationships: [
      {
        name: "addresses",
        peer: "IpamIPAddress",
        optional: false,
        cardinality: "many",
        kind: "Attribute",
      },
    ],
    label: "Task",
    inherit_from: ["BuiltinIPPrefix"],
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
        addresses {
          edges {
            node {
              id
              display_label
            }
          }
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
