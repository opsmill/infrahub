import Handlebars from "handlebars";
import "../../../utils/handlebars"; // Import handlebars utils

export const getObjectDetailsPaginated = Handlebars.compile(`
query {{kind}} {
  {{kind}} (ids: ["{{objectid}}"]) {
    edges {
      node {
        id
        display_label

        {{#if queryProfiles}}

        profiles {
          edges {
            node {
              display_label
              id
            }
          }
        }

        {{/if}}

        {{#each columns}}

          {{#if this.isAttribute}}

            {{this.name}} {
              value
              updated_at
              is_from_profile
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
              {{#if (eq this.kind "Dropdown")}}
              color
              description
              label
              {{/if}}
          }

          {{/if}}

          {{#if this.isRelationship}}

          {{this.name}}{{#if this.paginated}}(limit: 100){{/if}} {
            {{#if this.paginated}}
              edges {
            {{/if}}
              node {
                id
                display_label
                __typename
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
                __typename
              }
            {{#if this.paginated}}
            }
            {{/if}}
          }

          {{/if}}

          {{/each}}

        {{#if relationshipsTabs}}
          {{#each relationshipsTabs}}
            {{this.name}}(limit: 100) {
              count
            }
          {{/each}}
        {{/if}}
      }
    }
  }

  {{#if taskKind}}

  {{taskKind}}(related_node__ids: ["{{objectid}}"]) {
    count
  }

  {{/if}}

  {{#if profile}}

  {{profile}} {
    edges {
      node {
        id
        display_label
        __typename

        {{#each attributes}}
          {{this.name}} {
              value
              {{#if (eq this.kind "Dropdown")}}
              color
              description
              label
              {{/if}}
          }
        {{/each}}
      }
    }
  }

  {{/if}}
}
`);
