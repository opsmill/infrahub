import Handlebars from "handlebars";

export const updateObjectWithId = Handlebars.compile(`
mutation {{kind}}Update {
  {{kind}}Update (data: {{{data}}}) {
      ok
  }
}
`);
