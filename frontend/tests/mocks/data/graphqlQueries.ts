export const graphqlQueriesMocksQuery = `
query CoreGraphQLQuery {
  CoreGraphQLQuery(offset: 0, limit: 10) {
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
        repository {
          node {
            display_label
          }
        }
        tags {
          edges {
            node {
              display_label
            }
          }
        }
      }
    }
  }
}
`;

export const graphqlQueriesMocksQueryWithLimit = `
query CoreGraphQLQuery {
  CoreGraphQLQuery(offset: 0,limit: 50) {
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
          query {
              value
          }

          repository {
              node {
                display_label
              }
          }
          tags {
              edges {
                node {
                  display_label
                }
              }
          }
      }
    }
  }
}
`;

export const graphqlQueriesMocksData = {
  CoreGraphQLQuery: {
    count: 1000,
    edges: [
      {
        node: {
          id: "df844706-df55-4358-859c-c7882e54805f",
          display_label: "query-0001",
          name: {
            value: "query-0001",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0001 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-007",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "green",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "lime",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "maroon",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "c929ed61-b282-4d4c-9093-92b7b9ac602d",
          display_label: "query-0002",
          name: {
            value: "query-0002",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0002 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-007",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "green",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "lime",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "maroon",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "a5ac1fc9-6ddb-40a1-9084-67704dcdffc8",
          display_label: "query-0003",
          name: {
            value: "query-0003",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0003 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-007",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "green",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "lime",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "maroon",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "6bb6cc5d-9dff-4769-842f-4f53a5357d79",
          display_label: "query-0004",
          name: {
            value: "query-0004",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0004 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-007",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "green",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "lime",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "maroon",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "0aa3fd85-988a-496e-9710-0200a49d5791",
          display_label: "query-0005",
          name: {
            value: "query-0005",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0005 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-007",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "green",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "lime",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "maroon",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "fe88fbb4-2518-4b0d-9597-31ef6cfc0e77",
          display_label: "query-0006",
          name: {
            value: "query-0006",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0006 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-009",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "charcoal",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "magenta",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "silver",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "fc325729-7db9-4c6e-9984-9391a3df3bcd",
          display_label: "query-0007",
          name: {
            value: "query-0007",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0007 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-009",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "charcoal",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "magenta",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "silver",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "ce252a55-7ae0-4b06-932b-f45e1c89fa2d",
          display_label: "query-0008",
          name: {
            value: "query-0008",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0008 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-009",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "charcoal",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "magenta",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "silver",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "f6e05a07-3b2f-400e-bc19-cafc5639454d",
          display_label: "query-0009",
          name: {
            value: "query-0009",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0009 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-009",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "charcoal",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "magenta",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "silver",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "714b379a-290e-4d9e-acd3-fd02b2106799",
          display_label: "query-0010",
          name: {
            value: "query-0010",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0010 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-009",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "charcoal",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "magenta",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "silver",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
    ],
    __typename: "PaginatedGraphQLQuery",
  },
};

export const objectToDelete = "query-0001";

export const graphqlQueriesMocksDataDeleted = {
  CoreGraphQLQuery: {
    count: 999,
    edges: [
      {
        node: {
          id: "c929ed61-b282-4d4c-9093-92b7b9ac602d",
          display_label: "query-0002",
          name: {
            value: "query-0002",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0002 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-007",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "green",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "lime",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "maroon",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "a5ac1fc9-6ddb-40a1-9084-67704dcdffc8",
          display_label: "query-0003",
          name: {
            value: "query-0003",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0003 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-007",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "green",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "lime",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "maroon",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "6bb6cc5d-9dff-4769-842f-4f53a5357d79",
          display_label: "query-0004",
          name: {
            value: "query-0004",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0004 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-007",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "green",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "lime",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "maroon",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "0aa3fd85-988a-496e-9710-0200a49d5791",
          display_label: "query-0005",
          name: {
            value: "query-0005",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0005 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-007",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "green",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "lime",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "maroon",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "fe88fbb4-2518-4b0d-9597-31ef6cfc0e77",
          display_label: "query-0006",
          name: {
            value: "query-0006",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0006 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-009",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "charcoal",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "magenta",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "silver",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "fc325729-7db9-4c6e-9984-9391a3df3bcd",
          display_label: "query-0007",
          name: {
            value: "query-0007",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0007 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-009",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "charcoal",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "magenta",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "silver",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "ce252a55-7ae0-4b06-932b-f45e1c89fa2d",
          display_label: "query-0008",
          name: {
            value: "query-0008",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0008 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-009",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "charcoal",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "magenta",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "silver",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "f6e05a07-3b2f-400e-bc19-cafc5639454d",
          display_label: "query-0009",
          name: {
            value: "query-0009",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0009 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-009",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "charcoal",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "magenta",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "silver",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
      {
        node: {
          id: "714b379a-290e-4d9e-acd3-fd02b2106799",
          display_label: "query-0010",
          name: {
            value: "query-0010",
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            __typename: "TextAttribute",
          },
          query: {
            value: "query Query0010 { tag { name { value }}}",
            __typename: "TextAttribute",
          },
          repository: {
            node: {
              display_label: "repository-009",
              __typename: "Repository",
            },
            __typename: "NestedEdgedRepository",
          },
          tags: {
            edges: [
              {
                node: {
                  display_label: "charcoal",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "magenta",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  display_label: "silver",
                  __typename: "Tag",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "GraphQLQuery",
        },
        __typename: "EdgedGraphQLQuery",
      },
    ],
    __typename: "PaginatedGraphQLQuery",
  },
};
