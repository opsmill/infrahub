import Handlebars from "handlebars";

// TODO: Not working for now, needs the backend to be implemented
// const template = Handlebars.compile(`query {
//     branch (name: "{{banchName}}") {
//         id
//         name
//         description
//         origin_branch
//         branched_from
//         created_at
//         sync_with_git
//         is_default
//     }
// }
// `);

export const getBranchDetails = Handlebars.compile(`query {
  Branch {
      id
      name
      description
      origin_branch
      branched_from
      created_at
      sync_with_git
      is_default
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
}
`);
