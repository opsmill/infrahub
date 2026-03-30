import Handlebars from "@/shared/libs/handlebars";

export const getObjectDisplayLabel = Handlebars.compile(`
query GetLabel_{{kind}}($ids: [ID]) {
  {{kind}} (ids: $ids) {
    edges{
      node{
        id
        display_label
        {{#if peerField}}
        {{peerField}}{
          value
        }
        {{/if}}
      }
    }
  }
}
`);
