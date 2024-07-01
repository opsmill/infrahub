import Handlebars from "handlebars";

export const objectTreeQuery = Handlebars.compile(`
  query GET_{{kind}}_TREE {
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
