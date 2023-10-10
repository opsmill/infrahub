/// <reference types="cypress" />

import { ADMIN_CREDENTIALS, ENG_TEAM_ONLY_CREDENTIALS, READ_WRITE_CREDENTIALS } from "../utils";

describe("Protected fields", () => {
  beforeEach(() => {
    cy.visit("/");
  });

  it("should login and access the protected fields as admin", () => {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");

    cy.contains("Device").click();

    cy.contains("atl1-edge1").click();

    // Open the metadata tooltip
    cy.get(":nth-child(7) > .py-4 > .mt-1 > .p-2").click();

    // The owner should be the eng team
    cy.get(":nth-child(5) > .underline").should("have.text", ENG_TEAM_ONLY_CREDENTIALS.username);

    // Open the edit panel for the object
    cy.contains("Edit").click();

    // The input should be available
    cy.get("#headlessui-combobox-input-\\:r1g\\:").should("not.be.disabled");
  });

  it("should login and access the protected fields as owner", () => {
    cy.login(ENG_TEAM_ONLY_CREDENTIALS.username, ENG_TEAM_ONLY_CREDENTIALS.password);

    cy.visit("/");

    cy.contains("Device").click();

    cy.contains("atl1-edge1").click();

    // Open the metadata tooltip
    cy.get(":nth-child(7) > .py-4 > .mt-1 > .p-2").click();

    // The owner should be the eng team
    cy.get(":nth-child(5) > .underline").should("have.text", ENG_TEAM_ONLY_CREDENTIALS.username);

    // Open the edit panel for the object
    cy.contains("Edit").click();

    // The input should be available
    cy.get("#headlessui-combobox-input-\\:r1g\\:").should("not.be.disabled");
  });

  it("should login with write permissions but should not access the protecteed fields", () => {
    cy.login(READ_WRITE_CREDENTIALS.username, READ_WRITE_CREDENTIALS.password);

    cy.visit("/");

    cy.contains("Device").click();

    cy.contains("atl1-edge1").click();

    // Open the metadata tooltip
    cy.get(":nth-child(7) > .py-4 > .mt-1 > .p-2").click();

    // The owner should be the eng team
    cy.get(":nth-child(5) > .underline").should("have.text", ENG_TEAM_ONLY_CREDENTIALS.username);

    // Open the edit panel for the object
    cy.contains("Edit").click();

    // The input should be available
    cy.get("#headlessui-combobox-input-\\:r1g\\:").should("be.disabled");
  });
});
