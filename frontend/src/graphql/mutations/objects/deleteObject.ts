import Handlebars from "handlebars";

export const deleteObject = Handlebars.compile(`
mutation {{kind}}Delete {
  {{kind}}Delete (data: {{{data}}}) {
      ok
  }
}
`);
