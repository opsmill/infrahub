import Handlebars from "handlebars";

export const getProposedChanges = Handlebars.compile(`
query details {
  {{kind}}{{#if id}}(ids: ["{{id}}"]){{/if}} {
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

        threads {
          count
          edges {
            node {
              __typename
              id
              display_label
              resolved {
                value
              }
              created_by {
                node {
                  display_label
                }
              }
              comments {
                count
                edges {
                  node {
                    id
                    display_label
                    created_by {
                      node {
                        display_label
                      }
                    }
                    created_at {
                      value
                    }
                    text {
                      value
                    }
                  }
                }
              }
            }
          }
        }
        comments {
          count
          edges {
            node {
              __typename
              id
              display_label
              _updated_at
              created_by {
                node {
                  display_label
                }
              }
              created_at {
                value
              }
            }
          }
        }
      }
    }
  }
}
`);
