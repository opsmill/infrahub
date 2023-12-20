/// <reference types="cypress" />

import { ADMIN_CREDENTIALS } from "../utils";

const DEVICE_NAME = "den1-edge2";
const ETHERNET_NAME = "Ethernet11";
const ETHERNET_NEW_NAME = "Ethernet117";
const ETHERNET_SPEED = 10000;
const ETHERNET_NEW_SPEED = "100";

describe("Object update", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");
  });

  it("should update an object", function () {
    // Access the interfaces view
    cy.contains("Interface").click();

    // Access an interface
    cy.contains(DEVICE_NAME).click();

    // The name should be the original one
    cy.get(":nth-child(3) > div.items-center > .mt-1").should("have.text", ETHERNET_NAME);

    // The speed should be the original one
    cy.get(":nth-child(5) > div.items-center > .mt-1").should("have.text", ETHERNET_SPEED);

    // Open the edit panel
    cy.contains("Edit").click();

    // The name should be correctly defined in the input
    cy.get("#Name").should("have.value", ETHERNET_NAME);
    cy.get("#Name").clear();
    cy.get("#Name").type(ETHERNET_NEW_NAME, { delay: 0 });

    // The name should be correctly defined in the input
    cy.get("#Speed").should("have.value", ETHERNET_SPEED);
    cy.get("#Speed").clear();
    cy.get("#Speed").type(ETHERNET_NEW_SPEED, {
      delay: 0,
    });

    // Save
    cy.contains("Save").click();

    // Wait for the panel to be closed
    cy.get("[data-cy='side-panel-background']").should("not.exist");

    // The name should be the original one
    cy.get(":nth-child(3) > div.items-center > .mt-1").should("have.text", ETHERNET_NEW_NAME);

    // The speed should be the original one
    cy.get(":nth-child(5) > div.items-center > .mt-1").should("have.text", ETHERNET_NEW_SPEED);
  });
});
