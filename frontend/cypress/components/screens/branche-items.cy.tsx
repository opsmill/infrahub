/// <reference types="cypress" />

import React from "react";
import { BranchesItems } from "../../../src/screens/branches/branches-items";

describe("Branches screen", () => {
  it("should render the branch list correctly", () => {
    cy.mount(<BranchesItems />);
  });
});
