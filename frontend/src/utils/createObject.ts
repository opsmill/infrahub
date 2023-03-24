import { graphQLClient } from "..";
import { iNodeSchema } from "../state/atoms/schema.atom";

declare var Handlebars: any;

const mutationTemplate = Handlebars.compile(`mutation {{kind.value}}Create {
  {{name}}_create (data: {{{data}}}) {
      ok
  }
}
`);

const createObject = async (schema: iNodeSchema, updateObject: any[]) => {
  const createMutation = mutationTemplate({
    name: schema.name,
    data: JSON.stringify({
      ...updateObject,
    }).replace(/"([^"]+)":/g, "$1:"),
  });
  return graphQLClient.request(createMutation);
}

export default createObject;