import Handlebars from "@/shared/libs/handlebars";

export const createObject = Handlebars.compile(`mutation {{kind}}Create {
  {{kind}}Create (data: {{{data}}}) {
      object {
        id
        display_label
      }
      ok
  }
}
`);
