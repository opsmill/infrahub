import { gql } from "graphql-request";
import { graphQLClient } from "../../graphqlClient";
import { iNodeSchema } from "../../../state/atoms/schema.atom";

declare const Handlebars: any;

const template = Handlebars.compile(`query {{kind.value}} {
  {{name}} (ids: ["{{objectid}}"]) {
    {{relationship}} {
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
  }
}
`);

const getObjectRelationshipsDetails = async (schema: iNodeSchema, id: string, relationship: string) => {
  const queryString = template({
    ...schema,
    relationship,
    objectid: id,
  });

  const query = gql`
    ${queryString}
  `;

  const data: any = await graphQLClient.request(query);

  const rows = data[schema.name];

  if (rows.length) {
    return rows[0][relationship];
  } else {
    return null;
  }
};

export default getObjectRelationshipsDetails;
