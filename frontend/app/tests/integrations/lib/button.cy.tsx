/// <reference types="cypress" />

import React from "react";
import { BUTTON_TYPES, Button } from "../../../src/components/buttons/button";

describe("Button component", () => {
  it("should render VALIDATE button correctly", () => {
    cy.mount(<Button buttonType={BUTTON_TYPES.VALIDATE}>{"Validate"}</Button>);
  });

  it("should render WARNING button correctly", () => {
    cy.mount(<Button buttonType={BUTTON_TYPES.WARNING}>{"Warning"}</Button>);
  });

  it("should render CANCEL button correctly", () => {
    cy.mount(<Button buttonType={BUTTON_TYPES.CANCEL}>{"Cancel"}</Button>);
  });

  it("should render DEFAULT button correctly", () => {
    cy.mount(<Button>{"Default"}</Button>);
  });
});
