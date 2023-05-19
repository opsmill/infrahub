import Handlebars from "handlebars";

export type DiffOptions = {
  branch: string;
  time_from?: string;
  time_to?: string;
  branch_only?: boolean;
};

export const getDiff = Handlebars.compile(`
query {
  diff ({{{options}}}) {
    nodes {
      id
      kind
      changed_at
      action
      attributes {
        id
        name
        changed_at
        action
        properties {
          type
          changed_at
          action
          value {
            new
            previous
            __typename
          }
          __typename
        }
        __typename
      }
      __typename
  	}
    files {
      repository
      location
      action
      __typename
    }
    relationships {
      id
      name
      nodes {
        id
        kind
        __typename
      }
      properties {
        type
        changed_at
        action
        value {
          new
          previous
          __typename
        }
        __typename
      }
      changed_at
      action
      __typename
    }
  }
}
`);
