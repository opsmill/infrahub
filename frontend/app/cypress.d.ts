import { mount } from "cypress/react";

declare global {
  namespace Cypress {
    interface Chainable {
      mount: typeof mount;
      login: (username: string, password: string) => Chainable<any>;
    }
  }
}
