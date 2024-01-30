/// <reference types="cypress" />

import { ADMIN_CREDENTIALS } from "../constants";

describe.skip("Relationship Page", () => {
  it("should display object relationships without login", () => {
    cy.visit("/objects/InfraDevice");
    cy.contains("atl1-edge1").click();

    cy.contains("button", "Edit").should("be.disabled");
    cy.contains("button", "Manage groups").should("be.disabled");

    cy.contains("Artifacts2").click();
    cy.url().should("include", "tab=artifacts");
    cy.get("[data-cy='relationship-row']").should("have.length", 2);

    cy.contains("Interfaces14").click();
    cy.url().should("include", "tab=interfaces");
    cy.get("[data-cy='relationship-row']").should("have.length", 10);
    cy.contains("Showing 1 to 10 of 14 results").should("exist");
    cy.get("[data-cy='metadata-edit-button']").should("be.disabled");
    cy.get("[data-cy='relationship-delete-button']").should("be.disabled");
    cy.get("[data-cy='open-relationship-form-button']").should("be.disabled");
  });

  it("should create a new relationship", () => {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);
    cy.visit("/objects/InfraDevice");
    cy.contains("atl1-edge1").click();
    cy.contains("Interfaces").click();

    cy.get("[data-cy='open-relationship-form-button']").click();
    cy.contains("Add associated Interfaces").should("be.visible");

    // Form;
    cy.get("[data-cy='form']").within(() => {
      // fill 1st select by typing
      cy.get("[data-cy='select2step-2']").should("not.exist");
      cy.get("[data-cy='select2step-1']").type("Int");
      cy.contains("InterfaceL2").click();

      // fill 2nd select with click only
      // /!\ Is SUPER FLAKY !
      //  1. No easy visual way to differentiate each relationship "Ethernet11"
      //  2. Order of "Ethernet11" is not guaranteed to be the same each time
      cy.get("[data-cy='select2step-2']").should("be.visible");
      cy.get("[data-cy='select2step-2'] button").click();
      cy.contains("Ethernet11").click();

      cy.get("[data-cy='submit-form']").click();
    });

    cy.contains("Association with InfraInterface added").should("be.visible");
    cy.get("[data-cy='relationship-row']").contains("Ethernet11").should("be.visible");
    cy.contains("Showing 1 to 10 of 15 results").should("exist");
    cy.contains("Interfaces15").should("exist");
  });

  it("should update the new relationship", () => {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);
    cy.visit("/objects/InfraDevice");
    cy.contains("atl1-edge1").click();
    cy.contains("Interfaces").click();

    // get delete button from row containing Ethernet11
    // /!\ Is SUPER FLAKY !
    //  1. No easy visual way to differentiate each relationship "Ethernet11"
    //  2. Order of "Ethernet11" is not guaranteed to be the same each time
    cy.get("[data-cy='relationship-row']")
      .contains(/^Ethernet11$/)
      .parent()
      .within(() => {
        cy.get("[data-cy='metadata-edit-button']").click();
      });

    cy.get("[data-cy='form']").within(() => {
      cy.get("#Description").type("Test description");
      cy.contains("Save").click();
    });

    cy.contains("InterfaceL2 updated").should("be.visible");
    cy.get("[data-cy='relationship-row']")
      .contains(/^Ethernet11$/)
      .parent()
      .within(() => {
        cy.contains("Test description").should("be.visible");
      });
  });

  it("should delete the newly created relationship", () => {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);
    cy.visit("/objects/InfraDevice");
    cy.contains("atl1-edge1").click();
    cy.contains("Interfaces").click();

    cy.get("[data-cy='relationship-row']")
      .contains(/^Test description$/)
      .parent()
      .within(() => {
        cy.get("[data-cy='relationship-delete-button']").click();
      });

    // Modal delete
    cy.get("[data-cy='modal-delete']").within(() => {
      cy.contains(
        "Are you sure you want to remove the association between `atl1-edge1` and `Ethernet11`? The `InfraInterfaceL2` `Ethernet11` won't be deleted in the process."
      ).should("be.visible");
      cy.contains("button", "Delete").click();
    });

    // after delete
    cy.contains("Item removed from the group").should("be.visible");
    cy.contains("Showing 1 to 10 of 14 results").should("exist");
    cy.contains("Interfaces14").should("exist");
    cy.get("[data-cy='modal-delete']").should("not.exist");
    cy.get("[data-cy='relationship-row']").should("not.contain", /^Ethernet11$/);
  });
});
