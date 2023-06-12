/// <reference types="cypress" />

import { screenshotConfig } from "../utils";

describe("Tutorial - Part 3", () => {
  beforeEach(() => {
    cy.visit("/");
  });

  it("should access the schema list", () => {
    // Click on the schema link
    cy.get("#headlessui-disclosure-panel-\\:r3\\: > a > .group").click();

    cy.screenshot("tutorial_3_schema", screenshotConfig);
  });
});
