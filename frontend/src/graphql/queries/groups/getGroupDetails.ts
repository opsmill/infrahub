import Handlebars from "handlebars";

export const getGroupDetails = Handlebars.compile(`
query {{kind}} {
  {{kind}} (ids: ["{{groupid}}"]) {
    edges {
      node {
        id
        display_label

        {{#each attributes}}
          {{this.name}} {
              value
              updated_at
              is_protected
              is_visible
              source {
                id
                display_label
                __typename
              }
              owner {
                id
                display_label
                __typename
              }
          }
        {{/each}}

        members {
          count
        }

        subscribers {
          count
        }
      }
    }
  }
}
`);
