import Handlebars from "@/shared/libs/handlebars";

export const getProfileDetails = Handlebars.compile(`
query GET_PROFILE_DETAILS {
  AccountProfile {
    id
    display_label
    {{#each attributes}}
      {{this.name}} {
          value
          updated_at
          is_protected
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
  }
}
`);
