/// <reference types="cypress" />

import { ADMIN_CREDENTIALS } from "../utils";

const GROUP_NAME = "arista_devices";
const NEW_GROUP_1 = "Arista Devices";
const NEW_GROUP_2 = "Transit Interface";

const OBJECT_NAME = "atl1-edge2";

describe("Groups", () => {
  beforeEach(() => {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");
  });

  it("should list the groups and access to a group details", () => {
    // Access the group page
    cy.get("[href='/groups']").scrollIntoView();
    cy.get("[href='/groups']").click();

    // 5 groups should be present
    cy.get("div.flex > .text-sm > :nth-child(3)").should("have.text", "5");

    // Access group details
    cy.contains(GROUP_NAME).click();

    // Details should be fine in the header and in the deails page
    cy.get(".text-base").should("have.text", "StandardGroup");
    cy.get(".max-w-2xl").should("have.text", GROUP_NAME);
    cy.get(".sm\\:divide-y > :nth-child(2) > div.items-center > .mt-1").should(
      "have.text",
      GROUP_NAME
    );

    // Access the members
    cy.get(".-mb-px > :nth-child(2)").click();

    // There are 5 members
    cy.get("div.flex > .text-sm > :nth-child(3)").should("have.text", "20");
  });

  it("should add an object to 2 groups", () => {
    // Access the devices
    cy.get("[href='/objects/InfraDevice']").click();

    // Access the device details
    cy.contains(OBJECT_NAME).click();

    // Open the group side panel
    cy.contains("Manage groups").click();

    // The select should not contain any value
    cy.get("div[data-headlessui-state=''] > .relative > .w-full").should("not.have.text");

    // Open the select
    cy.get("[id^=headlessui-combobox-button-]").click();

    // CHeck if the options have a length of 6
    cy.get("[id^=headlessui-combobox-options-]").find("li").should("have.length", 11);

    // Choose 2 options
    cy.contains(NEW_GROUP_1).click();
    cy.contains(NEW_GROUP_2).click();

    // Save
    cy.contains("Save").click();
    cy.contains("Save").should("not.exist");

    // Open again the group side panel
    cy.contains("Manage groups").click();

    // The select must contains 4 items
    cy.get("div[data-headlessui-state=''] > .relative > .w-full")
      .find("span")
      .should("have.length", 2);

    // Close side panel
    cy.get("[data-cy='side-panel-background']").click();

    // Access the group page
    cy.get("[href='/groups']").scrollIntoView();
    cy.get("[href='/groups']").click();

    // Access group details
    cy.contains(GROUP_NAME).click();

    // Access the members
    cy.get(".-mb-px > :nth-child(2)").click();

    // There are 6 members
    cy.get("div.flex > .text-sm > :nth-child(3)").should("have.text", "6");

    cy.contains(OBJECT_NAME).should("exist");
  });

  it("should remove the same object from the previous groups", () => {
    // Access the devices
    cy.get("[href='/objects/InfraDevice'] > .group").click();

    // Access the device details
    cy.contains(OBJECT_NAME).click();

    // Open the group side panel
    cy.contains("Manage groups").click();

    // The select should contain 4 values
    cy.get("div[data-headlessui-state=''] > .relative > .w-full")
      .find("span")
      .should("have.length", 4);

    // Open the select
    cy.get("[id^=headlessui-combobox-button-]").click();

    // CHeck if the options have a length of 6
    cy.get("[id^=headlessui-combobox-options-]").find("li").should("have.length", 6);

    // Choose the 2 same options to remove the groups
    cy.contains(NEW_GROUP_1).click();
    cy.contains(NEW_GROUP_2).click();

    // Save
    cy.contains("Save").click();
    cy.contains("Save").should("not.exist");

    // Open again the group side panel
    cy.contains("Manage groups").click();

    // The select must contains 2 items
    cy.get("div[data-headlessui-state=''] > .relative > .w-full")
      .find("span")
      .should("have.length", 2);

    // Close side panel
    cy.get("[data-cy='side-panel-background']").click();

    // Access the group page
    cy.get("[href='/groups']").scrollIntoView();
    cy.get("[href='/groups']").click();

    // Access group details
    cy.contains(GROUP_NAME).click();

    // Access the members
    cy.get(".-mb-px > :nth-child(2)").click();

    // There are 5 members
    cy.get("div.flex > .text-sm > :nth-child(3)").should("have.text", "5");

    cy.contains(OBJECT_NAME).should("not.exist");
  });
});
