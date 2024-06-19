import Handlebars from "handlebars";

export const objectAncestorsQuery = Handlebars.compile(`
  query GET_{{kind}}_ANCESTORS {
    {{kind}}(limit: null) {
      edges {
        node {
          id
          display_label
          children {
            count
          }
          parent {
            node {
              id
              display_label
            }
          }
        }
      }
    }
  }
`);
