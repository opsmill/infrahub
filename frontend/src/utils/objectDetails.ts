import { gql } from "graphql-request";
import { graphQLClient } from "../graphql/graphqlClient";
import { iNodeSchema } from "../state/atoms/schema.atom";

declare const Handlebars: any;

const template = Handlebars.compile(`query {{kind.value}} {
    {{name}} (ids: ["{{objectid}}"]) {
        id
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
}
`);

const getObjectDetails = async (schema: iNodeSchema, id: string) => {
  const queryString = template({
    ...schema,
    objectid: id,
  });
  const query = gql`
    ${queryString}
  `;
  const data: any = await graphQLClient.request(query);
  const rows = data[schema.name];
  if (rows.length) {
    return rows[0];
  } else {
    return null;
  }
};

export default getObjectDetails;
