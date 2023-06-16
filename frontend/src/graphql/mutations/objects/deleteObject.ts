import Handlebars from "handlebars";

export const deleteObject = Handlebars.compile(`
mutation {{kind.value}}Update {
  {{name}}_delete (data: {{{data}}}) {
      ok
  }
}
`);
