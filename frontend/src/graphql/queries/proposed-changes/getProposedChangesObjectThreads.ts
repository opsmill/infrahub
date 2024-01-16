import Handlebars from "handlebars";

export const getProposedChangesObjectThreads = Handlebars.compile(`
query getProposedChangesThreadsFor{{kind}} {
  {{kind}}(
    change__ids: "{{id}}"
    object_path__value: "{{path}}"
  ) {
    count
    edges {
      node {
        __typename
        id
        comments {
          count
        }
      }
    }
  }
}
`);
