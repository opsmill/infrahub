import Handlebars from "handlebars";

export const subscription = Handlebars.compile(`
subscription Notification {
  query(name: "{{query}}", interval: 2)
}
`);
