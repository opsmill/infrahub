import Handlebars from "handlebars";

export const getProfileDetails = Handlebars.compile(`
query {{kind}} {
  {{kind}} (ids: ["{{objectid}}"]) {
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
          {{#each relationships}}
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
        {{/each}}
      }
    }
  }
}
`);

// export const getProfileDetails = Handlebars.compile(`
// query Account {
//   account {
//     edges {
//       node {
//         id
//         display_label
//         {{#each attributes}}
//           {{this.name}} {
//               value
//               updated_at
//               is_protected
//               is_visible
//               source {
//                 id
//                 display_label
//                 __typename
//               }
//               owner {
//                 id
//                 display_label
//                 __typename
//               }
//           }
//           {{/each}}
//           {{#each relationships}}
//             {{this.name}}{{#if this.paginated}}(limit: 100){{/if}} {
//               {{#if this.paginated}}
//                 edges {
//               {{/if}}
//                 node {
//                   id
//                   display_label
//                   __typename
//                 }
//                 properties {
//                   updated_at
//                   is_protected
//                   is_visible
//                   source {
//                     id
//                     display_label
//                     __typename
//                   }
//                   owner {
//                     id
//                     display_label
//                     __typename
//                   }
//                   __typename
//                 }
//               {{#if this.paginated}}
//               }
//               {{/if}}
//             }
//         {{/each}}
//       }
//     }
//   }
// }
// `);
