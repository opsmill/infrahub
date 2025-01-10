import Handlebars from "handlebars";

export const getTaskItemDetailsTitle = Handlebars.compile(`
query GetTaskDetails {
  {{kind}}(ids: ["{{id}}"]) {
    count
    edges {
      node {
        title
      }
    }
  }
}
`);
