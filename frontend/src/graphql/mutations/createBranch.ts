import { graphQLClient } from "../..";
import { objectToString } from "../../utils/common";

declare var Handlebars: any;

const mutationTemplate = Handlebars.compile(`
mutation branchCreate {
  branch_create (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);

const createBranch = async (data: any) => {
  const createMutation = mutationTemplate({
    data: objectToString(data)
  });

  return graphQLClient.request(createMutation);
};

export default createBranch;