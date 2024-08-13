import { gql } from "@apollo/client";

export const numberPoolQuery = gql`
  query GET_FORM_REQUIREMENTS($kind: String!) {
    CoreNumberPool(node__value: $kind) {
      edges {
        node {
          id
          display_label
          name {
            id
            value
          }
          node {
            id
            value
          }
          node_attribute {
            id
            value
          }
        }
      }
    }
  }
`;

export const numberPoolData = {
  data: {
    CoreNumberPool: {
      edges: [
        {
          node: {
            id: "17e8d40c-d2d4-95aa-2fa0-c51b6a309528",
            display_label: "test number pool",
            name: {
              id: "17e8d40c-f1d7-bc31-2fab-c51bdb00089d",
              value: "test number pool",
              __typename: "TextAttribute",
            },
            node: {
              id: "17e8d40c-f1d6-7052-2fac-c51583bc86de",
              value: "InfraInterfaceL3",
              __typename: "TextAttribute",
            },
            node_attribute: {
              id: "17e8d40c-f1d7-36ba-2fa6-c516fbfb65b2",
              value: "speed",
              __typename: "TextAttribute",
            },
            __typename: "CoreNumberPool",
          },
          __typename: "EdgedCoreNumberPool",
        },
      ],
      __typename: "PaginatedCoreNumberPool",
    },
  },
};
