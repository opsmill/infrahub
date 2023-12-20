/// <reference types="cypress" />

import { ADMIN_CREDENTIALS } from "../utils";

describe("Branches creation and deletion", () => {
  it("should not be able to create branch if not logged in", () => {
    cy.visit("/");
    cy.get("[data-cy='branch-select-menu']").contains("main");
    cy.get("[data-cy='create-branch-button']").should("be.disabled");
  });

  it("should create a new branch", () => {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);
    cy.visit("/");
    cy.get("[data-cy='create-branch-button']").click();

    // Form
    cy.contains("Create a new branch");
    cy.get("#new-branch-name").type("test123");
    cy.get("#new-branch-description").type("branch creation test");
    cy.contains("button", "Create").click();

    // After submit
    cy.get("[data-cy='branch-select-menu']").contains("test123");
    cy.url().should("include", "?branch=test123");
  });

  it("should display the new branch", () => {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);
    cy.visit("/");

    cy.get("[data-cy='branch-list-display-button']").click({ force: true });
    cy.get("[data-cy='branch-list-dropdown']").contains("test123");

    cy.get("[data-cy='sidebar-menu']").contains("Branches").click();
    cy.url().should("include", "/branches");

    cy.get("[data-cy='branches-items']").contains("test123").click();
    cy.url().should("include", "/branches/test123");
  });

  it("should delete a non-selected branch and remain on the current branch", () => {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);
    cy.createBranch("test456");
    cy.visit("/branches/test456?branch=test123");

    cy.contains("button", "Delete").click();

    cy.get("[data-cy='modal-delete']").within(() => {
      cy.contains("h3", "Delete").should("be.visible");
      cy.contains("Are you sure you want to remove the branch `test456`?").should("be.visible");
      cy.contains("button", "Delete").click();
    });

    cy.get("[data-cy='branch-select-menu']").contains("test123");
    cy.url().should("include", "/branches").and("include", "branch=test123");
    cy.get("[data-cy='branch-list-display-button']").click();
    cy.get("[data-cy='branch-list-dropdown']").contains("test123");
    cy.get("[data-cy='branch-list-dropdown']").contains("test456").should("not.exist");
  });

  it("should delete the currently selected branch", () => {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);
    cy.visit("/branches/test123?branch=test123");

    cy.contains("button", "Delete").click();

    cy.get("[data-cy='modal-delete']").within(() => {
      cy.contains("h3", "Delete").should("be.visible");
      cy.contains("Are you sure you want to remove the branch `test123`?").should("be.visible");
      cy.contains("button", "Delete").click();
    });

    cy.get("[data-cy='branch-select-menu']").contains("main");
    cy.url().should("not.include", "branch=test123");
    cy.get("[data-cy='branch-list-display-button']").click({ force: true });
    cy.get("[data-cy='branch-list-dropdown']").contains("main");
    cy.get("[data-cy='branch-list-dropdown']").contains("test123").should("not.exist");
  });
});
