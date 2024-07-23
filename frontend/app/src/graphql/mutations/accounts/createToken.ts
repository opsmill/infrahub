import Handlebars from "handlebars";

export const createToken = Handlebars.compile(`mutation CoreAccountTokenCreate {
  CoreAccountTokenCreate (data: {{{data}}}) {
      object {
        id
        token{
          value
        }
      }
      ok
  }
}
`);
