import Handlebars from "handlebars";

export const getObjectDisplayLabel = Handlebars.compile(`
query {{kind}} {
  {{kind}} (ids: ["{{id}}"]) {
    edges{
      node{
        display_label
      }
    }
  }
}
`);
