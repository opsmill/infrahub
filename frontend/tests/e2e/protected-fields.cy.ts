/// <reference types="cypress" />

import { ADMIN_CREDENTIALS, ENG_TEAM_ONLY_CREDENTIALS, READ_WRITE_CREDENTIALS } from "../constants";

describe("Protected fields", () => {
  beforeEach(() => {
    cy.visit("/");
  });

  it("should login and access the protected fields as admin", () => {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");

    cy.contains("All Device(s)").click();

    cy.contains("atl1-edge1").click();

    // Open the metadata tooltip
    cy.get(".sm\\:p-0").within(() => {
      cy.contains("Role")
        .parent()
        .within(() => {
          cy.get("[data-cy='metadata-button']").click();
        });
    });

    // The owner should be the eng team
    cy.get(":nth-child(5) > .underline").should("have.text", ENG_TEAM_ONLY_CREDENTIALS.username);

    // Open the edit panel for the object
    cy.contains("Edit").click();

    // Open the metadata tooltip
    cy.get("[data-cy='object-item-edit'").within(() => {
      cy.contains("Role")
        .parent()
        .parent()
        .within(() => {
          // The input should be available
          cy.get("input").should("not.be.disabled");
        });
    });
  });

  it("should login and access the protected fields as owner", () => {
    cy.login(ENG_TEAM_ONLY_CREDENTIALS.username, ENG_TEAM_ONLY_CREDENTIALS.password);

    cy.visit("/");

    cy.contains("All Device(s)").click();

    cy.contains("atl1-edge1").click();

    // Open the metadata tooltip
    cy.get(".sm\\:p-0").within(() => {
      cy.contains("Role")
        .parent()
        .within(() => {
          cy.get("[data-cy='metadata-button']").click();
        });
    });

    // The owner should be the eng team
    cy.get(":nth-child(5) > .underline").should("have.text", ENG_TEAM_ONLY_CREDENTIALS.username);

    // Open the edit panel for the object
    cy.contains("Edit").click();

    // Open the metadata tooltip
    cy.get("[data-cy='object-item-edit'").within(() => {
      cy.contains("Role")
        .parent()
        .parent()
        .within(() => {
          // The input should be available
          cy.get("input").should("not.be.disabled");
        });
    });
  });

  it("should login with write permissions but should not access the protecteed fields", () => {
    cy.login(READ_WRITE_CREDENTIALS.username, READ_WRITE_CREDENTIALS.password);

    cy.visit("/");

    cy.contains("All Device(s)").click();

    cy.contains("atl1-edge1").click();

    // Open the metadata tooltip
    cy.get(".sm\\:p-0").within(() => {
      cy.contains("Role")
        .parent()
        .within(() => {
          cy.get("[data-cy='metadata-button']").click();
        });
    });

    // The owner should be the eng team
    cy.get(":nth-child(5) > .underline").should("have.text", ENG_TEAM_ONLY_CREDENTIALS.username);

    // Open the edit panel for the object
    cy.contains("Edit").click();

    // Open the metadata tooltip
    cy.get("[data-cy='object-item-edit'").within(() => {
      cy.contains("Role")
        .parent()
        .parent()
        .within(() => {
          // The input should be available
          cy.get("input").should("be.disabled");
        });
    });
  });
});
