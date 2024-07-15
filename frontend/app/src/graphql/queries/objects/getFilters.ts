import Handlebars from "handlebars";

export const getFilters = Handlebars.compile(`query {{kind.value}} {
  {{name}} {
      id
      display_label
  }
}
`);
