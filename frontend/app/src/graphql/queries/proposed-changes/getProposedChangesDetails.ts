import Handlebars from "handlebars";

export const getProposedChanges = Handlebars.compile(`
query GET_PROPOSED_CHANGES($id: ID, $nodeId: String, $state: String) {
  {{kind}}(ids: [$id], state__value: $state) {
    count
    edges {
      node {
        id
        display_label
        __typename
        _updated_at

        {{#each attributes}}
          {{this.name}} {
              value
          }
        {{/each}}

        {{#each relationships}}
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
        {{/each}}

        comments{
          count
        }

        created_by {
          node {
            id
            display_label
          }
        }
      }
    }
  }

  {{#if accountKind}}

  {{accountKind}} {
    edges {
      node {
        id
        display_label
      }
    }
  }

  {{/if}}

  {{#if taskKind}}

  {{taskKind}}(related_node__ids: [$nodeId]) {
    count
  }

  {{/if}}
}
`);
