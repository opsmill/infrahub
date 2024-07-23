export const getTokens = `
query CoreAccountToken($offset: Int, $limit: Int) {
  CoreAccountToken(offset: $offset, limit: $limit) {
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
