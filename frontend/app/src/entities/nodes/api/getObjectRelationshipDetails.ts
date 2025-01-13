import Handlebars from "handlebars";

export const getObjectRelationshipsDetailsPaginated = Handlebars.compile(`
query GetObjectRelationships_{{kind}}($offset: Int, $limit: Int) {
  {{kind}} (ids: ["{{objectid}}"]) {
    count
    edges {
      node {
        {{relationship}}(
          offset: $offset
          limit: $limit
        ) {
          count
          edges {
            node {
              id
              display_label
              __typename

              {{#if relationshipKind}} ... on {{relationshipKind}} { {{/if}}

                {{#each columns}}

                {{#if this.isAttribute}}

                {{this.name}} {
                  id
                  value
                  {{#if (eq this.kind "Dropdown")}}
                  color
                  description
                  label
                  {{/if}}
                }

                {{/if}}

                {{#if this.isRelationship}}

                {{this.name}} {
                  {{#if this.paginated}}
                    edges {
                  {{/if}}
                    node {
                      id
                      display_label
                    }
                  {{#if this.paginated}}
                    }
                  {{/if}}
                }

                {{/if}}

                {{/each}}

              {{#if relationshipKind}} } {{/if}}

            }

            properties {
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

            properties {
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
          }
        }
      }
    }
  }
}
`);
