declare const Handlebars: any;

export const createObject = Handlebars.compile(`mutation {{kind.value}}Create {
  {{name}}_create (data: {{{data}}}) {
      ok
  }
}
`);
