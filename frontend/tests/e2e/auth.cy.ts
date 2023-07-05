/// <reference types="cypress" />

import { ADMIN_CREDENTIALS, READ_ONLY_CREDENTIALS, READ_WRITE_CREDENTIALS } from "../utils";

describe("Authentication", () => {
  beforeEach(() => {
    cy.visit("/");
  });

  it("should login as read-write role and have write access", () => {
    cy.login(READ_WRITE_CREDENTIALS.username, READ_WRITE_CREDENTIALS.password);

    cy.visit("/");

    // The branch creation button should not be disabled
    cy.get("#headlessui-popover-button-\\:r8\\: > .py-1\\.5").should("not.be.disabled");

    // The avatar should have the intials
    cy.get(".h-12").should("have.text", "CO");
  });

  it("should login as read-only role and have read-only access", () => {
    cy.login(READ_ONLY_CREDENTIALS.username, READ_ONLY_CREDENTIALS.password);

    cy.visit("/");

    // The branch creation button should be disabled
    cy.get("#headlessui-popover-button-\\:r8\\: > .py-1\\.5").should("be.disabled");

    // The avatar should have the intials
    cy.get(".h-12").should("have.text", "JB");
  });

  it("should access the profile page", () => {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");

    // Click on the avatar
    cy.get(".h-12").click();

    // Click on the profile button
    cy.get("#headlessui-menu-item-\\:rc\\:").click();

    // The name in the header should be the one from the user auth
    cy.get(".text-base").should("have.text", "Admin");

    // The name in the details should be the one from the user auth
    cy.get(":nth-child(2) > div.items-center > .mt-1").should(
      "have.text",
      ADMIN_CREDENTIALS.username
    );

    // Click on the token tab
    cy.get(".-mb-px > .border-transparent").click();

    // Check if a token exists
    cy.get(".hover\\:bg-gray-50 > :nth-child(2)").should("exist");
  });
});
