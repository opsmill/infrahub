import { graphQLClient } from "../../graphqlClient";
import { objectToString } from "../../../utils/common";

declare const Handlebars: any;

const mutationTemplate = Handlebars.compile(`
mutation {
  branch_validate (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);

const validateBranch = async (data: any) => {
  console.log("data: ", data);
  const mutation = mutationTemplate({
    data: objectToString(data)
  });

  return graphQLClient.request(mutation);
};

export default validateBranch;