import Handlebars from "handlebars";

export const addRelationship = Handlebars.compile(`
mutation RelationshipAdd {
  RelationshipAdd (data: {{{data}}}) {
      ok
  }
}
`);
