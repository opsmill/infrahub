declare const Handlebars: any;

export const updateObjectWithId = Handlebars.compile(`
mutation {{kind.value}}Update {
  {{name}}_update (data: {{{data}}}) {
      ok
  }
}
`);
