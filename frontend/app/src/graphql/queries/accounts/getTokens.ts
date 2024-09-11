export const getTokens = `
query InfrahubAccountToken($offset: Int, $limit: Int) {
  InfrahubAccountToken(offset: $offset, limit: $limit) {
    count
    edges {
      node {
        id
        name
        expiration
      }
      __typename
    }
    __typename
  }
}
`;
