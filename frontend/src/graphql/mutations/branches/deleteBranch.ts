import { graphQLClient } from "../../graphqlClient";
import { objectToString } from "../../../utils/common";

declare const Handlebars: any;

const mutationTemplate = Handlebars.compile(`
mutation {
  branch_delete (
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