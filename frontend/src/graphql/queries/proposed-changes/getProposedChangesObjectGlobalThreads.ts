import Handlebars from "handlebars";

export const getProposedChangesObjectGlobalThreads = Handlebars.compile(`
query {
  {{kind}}(
    change__ids: "{{id}}"
  ) {
    count
    edges {
      node {
        __typename
        id
        object_path {
          value
        }
        comments {
          count
        }
      }
    }
  }
}
`);
