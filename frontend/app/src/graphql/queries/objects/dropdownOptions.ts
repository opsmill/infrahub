import Handlebars from "handlebars";

export const getDropdownOptions = Handlebars.compile(`query DropdownOptions {
  {{kind}} {
    count
    edges {
      node {
        id
        display_label
        __typename
      }
    }
  }
}`);
