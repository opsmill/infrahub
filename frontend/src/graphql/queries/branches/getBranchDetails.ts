import Handlebars from "handlebars";

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

export const getBranchDetails = Handlebars.compile(`query {
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
