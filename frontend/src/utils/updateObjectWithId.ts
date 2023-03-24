import { graphQLClient } from "..";
import { iNodeSchema } from "../state/atoms/schema.atom";

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
    data: JSON.stringify({
      id,
      ...updateObject,
    }).replace(/"([^"]+)":/g, "$1:"),
  });
  return graphQLClient.request(updateMutation);
}

export default updateObjectWithId;