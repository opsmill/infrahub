import Handlebars from "handlebars";

export const getRelationshipParent = Handlebars.compile(`
  query GET_RELATIONSHIP_PARENT {
    {{kind}}({{attribute}}: ["{{id}}"]) {
      count
      edges {
        node {
          id
          display_label
        }
      }
    }
  }
`);
