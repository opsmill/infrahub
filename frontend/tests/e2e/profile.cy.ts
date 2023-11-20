/// <reference types="cypress" />

import { ADMIN_CREDENTIALS } from "../utils";

describe("Profile page", () => {
  it("should access and display all information's about user", () => {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);
    cy.visit("/");

    cy.get("[data-cy='user-avatar']").click();
    cy.contains("Your Profile").click();
    cy.url().should("include", "/profile");

    cy.get("[data-cy='user-details']").within(() => {
      cy.contains("Name").next().should("contain", "admin");
      cy.contains("Label").next().should("contain", "Admin");
      cy.contains("Description").next().should("contain", "");
      cy.contains("Type").next().should("contain", "User");
      cy.contains("Role").next().should("contain", "admin");
    });

    cy.contains("Preference").click();
    cy.url().should("include", "tab=preferences");
    cy.contains("Update your password").should("be.visible");
  });
});
