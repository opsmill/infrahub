/// <reference types="cypress" />

import React from "react";
import { PILL_TYPES, Pill } from "../../../src/components/display/pill";

describe("Pill component", () => {
  it("should render VALIDATE pill correctly", () => {
    cy.mount(<Pill type={PILL_TYPES.VALIDATE}>{"Validate"}</Pill>);
  });

  it("should render WARNING pill correctly", () => {
    cy.mount(<Pill type={PILL_TYPES.WARNING}>{"Warning"}</Pill>);
  });

  it("should render CANCEL pill correctly", () => {
    cy.mount(<Pill type={PILL_TYPES.CANCEL}>{"Cancel"}</Pill>);
  });

  it("should render DEFAULT pill correctly", () => {
    cy.mount(<Pill>{"Default"}</Pill>);
  });
});
