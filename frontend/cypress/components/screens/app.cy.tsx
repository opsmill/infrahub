import React from "react";
import App from "../../../src/App";

declare const cy: any;

describe("Branches screen", () => {

  it("should render the branch list correctly", () => {
    cy.viewport(1920, 1080);

    cy.mount(
      <App />
    );
  });
});
