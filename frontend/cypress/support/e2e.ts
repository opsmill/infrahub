/// <reference types="cypress" />

// ***********************************************************
// This example support/e2e.ts is processed and
// loaded automatically before your test files.
//
// This is a great place to put global configuration and
// behavior that modifies Cypress.
//
// You can change the location of this file or turn off
// automatically serving support files with the
// 'supportFile' configuration option.
//
// You can read more here:
// https://on.cypress.io/configuration
// ***********************************************************

// Import commands.js using ES2015 syntax:
import "./commands";

// Alternatively you can use CommonJS syntax:
// require('./commands')

Cypress.Commands.add("login", (username: string, password: string) => {
  cy.visit("/signin");

  cy.get(":nth-child(1) > .relative > .block").type(username);

  cy.get(":nth-child(2) > .relative > .block").type(password);

  cy.get(".mt-6 > .rounded-md").click();
});
