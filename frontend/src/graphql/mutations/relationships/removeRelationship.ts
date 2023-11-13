import Handlebars from "handlebars";

export const removeRelationship = Handlebars.compile(`
mutation RelationshipRemove {
  RelationshipRemove (data: {{{data}}}) {
      ok
  }
}
`);
