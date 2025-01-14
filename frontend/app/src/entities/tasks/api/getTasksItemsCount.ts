import Handlebars from "handlebars";

export const getTasksItemsCount = Handlebars.compile(`
query GetTasks {
  {{kind}} {
    count
  }
}
`);
