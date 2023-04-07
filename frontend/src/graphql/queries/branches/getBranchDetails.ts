import { gql } from "graphql-request";
import { graphQLClient } from "../../graphqlClient";
import { Branch } from "../../../generated/graphql";

declare const Handlebars: any;

type BranchResult = {
  branch: Branch[]
}

// const template = Handlebars.compile(`query {
//     branch (id: "{{objectid}}") {
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

const getBranchDetails = async (id: string) => {
  const queryString = template({
    objectid: id,
  });

  const query = gql`
    ${queryString}
  `;

  const data: BranchResult = await graphQLClient.request(query);

  const currentBranch = data?.branch?.filter((branch: any) => branch.id === id)[0];

  return currentBranch;
};

export default getBranchDetails;
