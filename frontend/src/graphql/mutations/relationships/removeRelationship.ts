import Handlebars from "handlebars";

export const removeRelationship = Handlebars.compile(`
mutation relationship_remove {
  relationship_remove (data: {{{data}}}) {
      ok
  }
}
`);
