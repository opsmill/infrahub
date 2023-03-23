import { graphQLClient } from "..";
import { iNodeSchema } from "../state/atoms/schema.atom";

declare var Handlebars: any;

const mutationTemplate = Handlebars.compile(`mutation {{kind.value}}Create {
  {{name}}_create (data: { 
    {{{arguments}}} 
  }) {
      ok
  }
}
`);

const createObject = async (schema: iNodeSchema, mutationArgs: any[]) => {
  const createMutation = mutationTemplate({
    name: schema.name,
    arguments: mutationArgs.join(","),
  });
  return graphQLClient.request(createMutation);
}

export default createObject;