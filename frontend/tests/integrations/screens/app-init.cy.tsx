/// <reference types="cypress" />

import React from "react";
import App from "../../../src/App";

describe("Config fetch", () => {
  beforeEach(function () {
    cy.fixture("login").as("login");
    cy.fixture("config").as("config");
    cy.fixture("schema").as("schema");
  });

  it("should login and load the config", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/auth/login", this.login).as("login");

    cy.intercept("GET", "/config", this.config).as("getConfig");

    cy.intercept("GET", "/schema", this.schema).as("getSchema");

    cy.mount(<App />);

    cy.get(":nth-child(1) > .relative > .block").type("test");

    cy.get(":nth-child(2) > .relative > .block").type("test");

    cy.get(".mt-6 > .rounded-md").click();

    cy.wait("@login").then(({ response }) => {
      expect(response?.body?.access_token).to.exist;
    });

    cy.wait("@getSchema").then(({ response }) => {
      const schemaArray = response?.body?.nodes;

      expect(schemaArray).to.have.lengthOf(1);
    });

    cy.get("#headlessui-disclosure-panel-\\:r3\\: > a > .group").should("have.text", "Device");
  });
});
