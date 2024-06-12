import Handlebars from "handlebars";

export const basicMutation = Handlebars.compile(`mutation {
  {{kind}} (data: {{{data}}}) {
      ok
  }
}
`);
