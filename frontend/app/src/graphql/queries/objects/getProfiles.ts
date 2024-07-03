import Handlebars from "handlebars";

export const getProfiles = Handlebars.compile(`
  query GetProfiles {
    {{#each profiles}}

    {{this}} {

      edges{
        node{
          id
          display_label
        }
      }
    }

    {{/each}}

  }
`);
