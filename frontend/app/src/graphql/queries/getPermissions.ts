import Handlebars from "handlebars";

export const getPermissions = Handlebars.compile(`
  query GET_PERMISSIONS {
    {{kind}}{
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
