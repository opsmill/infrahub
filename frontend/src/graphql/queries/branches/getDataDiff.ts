import { graphQLClient } from "../../graphqlClient";
import { objectToString } from "../../../utils/common";

declare const Handlebars: any;

type DiffOptions = {
  branch: string;
  time_from?: string;
  time_to?: string;
  branch_only?: boolean;
}

const queryTemplate = Handlebars.compile(`
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
  }
}
`);

const getDataDiff = async (options: DiffOptions) => {
  const query = queryTemplate({
    options: objectToString(options)
  });

  const result: any = await graphQLClient.request(query);

  return result?.diff;
};

export default getDataDiff;