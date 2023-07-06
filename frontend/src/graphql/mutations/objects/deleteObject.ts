import Handlebars from "handlebars";

export const deleteObject = Handlebars.compile(`
mutation {{kind}}Update {
  {{kind}}Delete (data: {{{data}}}) {
      ok
  }
}
`);
