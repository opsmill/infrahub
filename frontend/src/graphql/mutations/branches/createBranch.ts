import { graphQLClient } from "../../..";
import { objectToString } from "../../../utils/common";

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
  const mutation = mutationTemplate({
    data: objectToString(data)
  });

  return graphQLClient.request(mutation);
};

export default createBranch;