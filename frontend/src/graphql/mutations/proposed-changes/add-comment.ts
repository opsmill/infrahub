import Handlebars from "handlebars";

export const addComment = Handlebars.compile(`
mutationString:  mutation Create {
  CoreChangeCommentCreate (data: {
    text: {
        value: "aze"
    },
    created_at: {
        value: null
    },
    change: {
        id: "21a6e070-dbdd-4afd-b8fa-47e31d413979"
    }
}) {
      ok
  }
}
`);
