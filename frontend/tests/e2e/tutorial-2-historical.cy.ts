/// <reference types="cypress" />

import { NEW_ADMIN_ACCOUNT_LABEL } from "../mocks/e2e/accounts";

describe("Tutorial - Part 2", () => {
  beforeEach(() => {
    cy.viewport(1920, 1080);

    cy.visit("/");
  });

  it("should check the historical data", () => {
    // Access the accounts list
    cy.get("[href='/objects/account'] > .group").click();

    // Access admin account
    cy.get(".bg-white > :nth-child(5) > :nth-child(1)").click();

    // The label should be the new one
    cy.get(":nth-child(4) > div.flex > .mt-1").should("have.text", NEW_ADMIN_ACCOUNT_LABEL);

    // TODO: Define a previous date and verify if the label is correctly the old one
  });
});
