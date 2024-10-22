import Handlebars from "handlebars";

export const getDropdownOptions = Handlebars.compile(`query DropdownOptions {
  {{kind}}{{#if parentFilter}}({{{parentFilter}}}){{/if}}  {
    count
    edges {
      node {
        id
        display_label
        {{#if peerField}}
        {{peerField}}{
          value
        }
        {{/if}}
        __typename
      }
    }
  }
}`);
