import Handlebars from "handlebars";

export const updateObjectDetails = Handlebars.compile(`query {{kind.value}} {
    {{name}} (ids: ["{{objectid}}"]) {
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
        {{#each relationships}}
        {{this.name}} {
            id
            display_label
            __typename
            _relation__is_visible
            _relation__is_protected
            _updated_at
            _relation__owner {
              id
              display_label
              __typename
            }
            _relation__source {
              id
              display_label
              __typename
            }
        }
        {{/each}}
    }
    {{#each peers}}
    {{this}} {
        id
        display_label
    }
    {{/each}}
}
`);
