/// <reference types="cypress" />

describe("Main application", () => {
  it("should load", () => {
    cy.visit("/");

    // The first item should be Account
    cy.get("[href='/objects/Account'] > .group").should("have.text", "Account");

    // The branch selector should display the main branch
    cy.get(".ml-2\\.5").should("have.text", "main");
  });
});
