/// <reference types="cypress" />

describe("Tutorial - Part 4", () => {
  beforeEach(() => {
    cy.viewport(1920, 1080);

    cy.visit("/");
  });

  it("should verify the metadata from the demo dataset", () => {
    // Access to the devices
    cy.get("[href='/objects/device'] > .group").click();

    // Click on a device
    cy.contains("atl1-edge1").click();

    // Click to open the metadata for the name
    cy.get(".sm\\:p-0 > :nth-child(1) > :nth-child(2) > div.items-center > .relative").click();
    cy.get(":nth-child(4) > .underline").should("have.text", "Pop-Builder");
    cy.get(".sm\\:p-0 > :nth-child(1) > :nth-child(2) > div.items-center > .relative").click(); // Close the popin

    // Click to open the metadata for the role
    cy.get(":nth-child(7) > .py-4 > .mt-1 > .relative").click();
    cy.get(":nth-child(5) > .underline").should("have.text", "Engineering Team");
    cy.get(":nth-child(7) > .py-4 > .mt-1 > .relative").click(); // Close the popin

    // Click to open the metadata for a tag
    cy.get(".sm\\:col-span-2 > :nth-child(1) > .relative").click();
    cy.get(":nth-child(5) > :nth-child(2)").should("have.text", "False");
    cy.get(".sm\\:col-span-2 > :nth-child(1) > .relative").click(); // Close the popin
  });
});
