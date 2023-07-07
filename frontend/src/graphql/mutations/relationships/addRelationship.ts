import Handlebars from "handlebars";

export const addRelationship = Handlebars.compile(`
mutation relationship_add {
  relationship_add (data: {{{data}}}) {
      ok
  }
}
`);
