import { graphQLClient } from "..";
import { iNodeSchema } from "../state/atoms/schema.atom";
import { getStringJSONWithoutQuotes } from "./getStringJSONWithoutQuotes";

declare var Handlebars: any;

const mutationTemplate = Handlebars.compile(`mutation {{kind.value}}Update {
  {{name}}_update (data: {{{data}}}) {
      ok
  }
}
`);

const updateObjectWithId = async (id: string, schema: iNodeSchema, updateObject: object) => {
  const updateMutation = mutationTemplate({
    name: schema.name,
    data: getStringJSONWithoutQuotes({
      id,
      ...updateObject,
    }),
  });
  console.log(updateMutation);
  return graphQLClient.request(updateMutation);
};

export default updateObjectWithId;