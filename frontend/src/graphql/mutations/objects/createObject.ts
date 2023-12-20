import Handlebars from "handlebars";

export const createObject = Handlebars.compile(`mutation {{kind.value}}Create {
  {{kind}}Create (data: {{{data}}}) {
      object {
        id
        display_label
      }
      ok
  }
}
`);
