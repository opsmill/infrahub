import { graphQLClient } from "../graphql/graphqlClient";
import { iNodeSchema } from "../state/atoms/schema.atom";
import { getStringJSONWithoutQuotes } from "./getStringJSONWithoutQuotes";

declare const Handlebars: any;

const mutationTemplate = Handlebars.compile(`mutation {{kind.value}}Create {
  {{name}}_create (data: {{{data}}}) {
      ok
  }
}
`);

const createObject = async (schema: iNodeSchema, updateObject: any[]) => {
  const mutation = mutationTemplate({
    name: schema.name,
    data: getStringJSONWithoutQuotes(updateObject),
  });
  return graphQLClient.request(mutation);
};

export default createObject;
