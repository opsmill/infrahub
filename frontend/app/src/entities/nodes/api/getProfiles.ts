import Handlebars from "@/shared/libs/handlebars";

export const getProfiles = Handlebars.compile(`
  query GetProfiles {
    {{#each profiles}}

    {{this.name}} {

      edges{
        node{
          id
          display_label

          {{#each this.attributes}}

            {{this.name}} {
                value
                {{#if (eq this.kind "Dropdown")}}
                color
                description
                label
                {{/if}}
            }

          {{/each}}

          {{#each this.relationships}}

            {{this.name}} {
              {{#if this.paginated}}
              edges {
                node {
                  id
                  display_label
                  hfid
                  __typename
                }
              }
              {{else}}
              node {
                id
                display_label
                hfid
                __typename
              }
              {{/if}}
            }

          {{/each}}

        }
      }
    }

    {{/each}}

  }
`);
