import { gql } from "graphql-request";
import { iGenericSchema, iNodeSchema } from "../../../state/atoms/schema.atom";
import { getAttributeColumnsFromNodeOrGenericSchema } from "../../../utils/getSchemaObjectColumns";
import { graphQLClient } from "../../graphqlClient";

declare const Handlebars: any;

const template = Handlebars.compile(`query {{kind.value}} {
  {{name}} (ids: ["{{objectid}}"]) {
    {{relationship}} {
      id
      display_label
      {{#each columns}}
      {{this.name}} {
        value
      }
      {{/each}}
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

const getObjectRelationshipsDetails = async (schema: iNodeSchema, schemaList: iNodeSchema[], generics: iGenericSchema[], id: string, relationship: string) => {
  const relationshipSchema = schema.relationships?.find((r) => r?.name === relationship);
  const columns = getAttributeColumnsFromNodeOrGenericSchema(schemaList, generics, relationshipSchema?.peer!);

  const queryString = template({
    ...schema,
    relationship,
    objectid: id,
    columns,
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
