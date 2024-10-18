import Handlebars from "handlebars";

export const getGroupsQuery = Handlebars.compile(`
query GET_GROUPS {
  {{objectKind}}(ids:["{{objectId}}"]) {
    edges {
      node {
        member_of_groups {
          count
          edges {
            node {
              id
              display_label
              description {
                value
              }
              group_type {
                value
              }
              members {
                count
              }
            }
          }
        }
      }
    }
    permissions {
      edges {
        node {
          kind
          view
          create
          update
          delete
        }
      }
    }
  }
}
`);
