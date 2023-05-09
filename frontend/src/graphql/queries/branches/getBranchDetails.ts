import { gql } from "graphql-request";
import { graphQLClient } from "../../graphqlClient";
import { Branch } from "../../../generated/graphql";

declare const Handlebars: any;

type BranchResult = {
  branch: Branch[];
};

// TODO: Not working for now, needs the backend to be implemented
// const template = Handlebars.compile(`query {
//     branch (name: "{{banchName}}") {
//         id
//         name
//         description
//         origin_branch
//         branched_from
//         created_at
//         is_data_only
//         is_default
//     }
// }
// `);

const template = Handlebars.compile(`query {
  branch {
      id
      name
      description
      origin_branch
      branched_from
      created_at
      is_data_only
      is_default
  }
}
`);

const getBranchDetails = async (name: string) => {
  const queryString = template({
    banchName: name,
  });

  const query = gql`
    ${queryString}
  `;

  const data: BranchResult = await graphQLClient.request(query);

  // TODO: Remove filter once the details query is working
  const currentBranch = data?.branch?.filter((branch: any) => branch.name === name)[0];

  return currentBranch;
};

export default getBranchDetails;
