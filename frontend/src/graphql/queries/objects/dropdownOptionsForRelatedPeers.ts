import Handlebars from "handlebars";

export interface iPeerDropdownOption {
  id: string;
  display_label: string;
}

export interface iPeerDropdownOptions {
  [peer: string]: iPeerDropdownOption[];
}

export const getDropdownOptionsForRelatedPeersPaginated =
  Handlebars.compile(`query DropdownFormOptions {
  {{#each peers}}
  {{this}} {
    count
    edges {
      node {
        id
        display_label
        __typename
      }
    }
  }
  {{/each}}
}`);
