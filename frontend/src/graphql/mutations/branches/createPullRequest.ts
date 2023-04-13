import { graphQLClient } from "../../graphqlClient";
import { objectToString } from "../../../utils/common";

declare const Handlebars: any;

const mutationTemplate = Handlebars.compile(`
mutation {
  branch_create (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);

const createPullRequest = async (data: any) => {
  const mutation = mutationTemplate({
    data: objectToString(data)
  });

  return graphQLClient.request(mutation);
};

export default createPullRequest;