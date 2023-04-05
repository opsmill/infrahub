import Handlebars from "handlebars";
import { graphQLClient } from "../../../graphqlClient";
import { objectToString } from "../../../utils/common";

const mutationTemplate = Handlebars.compile(`
mutation {
  branch_create (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);

const deleteBranch = async (data: any) => {
  const mutation = mutationTemplate({
    data: objectToString(data)
  });

  return graphQLClient.request(mutation);
};

export default deleteBranch;