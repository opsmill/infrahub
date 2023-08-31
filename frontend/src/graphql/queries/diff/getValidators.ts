import Handlebars from "handlebars";

export const getValidators = Handlebars.compile(`
query {
  CoreValidator(
    proposed_change__ids: ["{{id}}"]
  ) {
    edges {
      node {
        id
        display_label
        conclusion {
          value
        }
        started_at {
          value
        }
        completed_at {
          value
        }
        state {
          value
        }
        checks {
          count
        }
      }
    }
  }
}

`);
