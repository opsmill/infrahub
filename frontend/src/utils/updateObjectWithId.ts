import { graphQLClient } from "..";
import { iNodeSchema } from "../state/atoms/schema.atom";

declare var Handlebars: any;

const mutationTemplate = Handlebars.compile(`mutation {{kind.value}}Update {
  {{name}}_update (data: {
    id: "{{id}}", {{{arguments}}}
  }) {
      ok
  }
}
`);

const updateObjectWithId = async (id: string, schema: iNodeSchema, mutationArgs: any[]) => {
  const updateMutation = mutationTemplate({
    name: schema.name,
    id,
    arguments: mutationArgs.join(","),
  });
  return graphQLClient.request(updateMutation);
};

export default updateObjectWithId;