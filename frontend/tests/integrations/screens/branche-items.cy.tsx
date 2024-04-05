/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import BranchesItems from "../../../src/screens/branches/branches-items";
import { branchesState } from "../../../src/state/atoms/branches.atom";
import { branchesMocks, branchesQuery } from "../../mocks/data/branches";
import { TestProvider } from "../../mocks/jotai/atom";

// Mock the apollo query and data (unused)
const mocks: any[] = [
  {
    request: {
      query: gql`
        ${branchesQuery}
      `,
    },
    result: {
      data: branchesMocks,
    },
  },
];

// Provide the initial value for jotai
const BranchesProvider = () => {
  return (
    <TestProvider initialValues={[[branchesState, branchesMocks]]}>
      <BranchesItems />
    </TestProvider>
  );
};

describe("Branches screen", () => {
  it("should render the branch list correctly", () => {
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <BranchesProvider />
      </MockedProvider>
    );

    cy.contains(`Branches${branchesMocks.length}`).should("exist");
  });
});
