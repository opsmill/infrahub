/// <reference types="cypress" />

import { ADMIN_CREDENTIALS } from "../utils";

describe("Main application", () => {
  beforeEach(() => {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");
  });

  it("should load", () => {
    // The first item should be Account
    cy.get("[href='/objects/Account'] > .group").should("have.text", "Account");

    // The branch selector should display the main branch
    cy.get(".ml-2\\.5").should("have.text", "main");
  });
});
