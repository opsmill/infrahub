import Handlebars from "@/shared/libs/handlebars";

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
