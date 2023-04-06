import React from "react";
import {BranchesItems} from "../../../src/screens/branches/branches-items";

declare const cy: any;

describe("Branches screen", () => {
  it("should render the branch list correctly", () => {
    cy.mount(
      <BranchesItems />
    );
  });
});
