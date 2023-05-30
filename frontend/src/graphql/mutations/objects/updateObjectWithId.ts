import Handlebars from "handlebars";

export const updateObjectWithId = Handlebars.compile(`
mutation {{kind.value}}Update {
  {{name}}_update (data: {{{data}}}) {
      ok
  }
}
`);
