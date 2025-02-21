/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import { Route, Routes } from "react-router";
import { proposedChangedState } from "../../../src/entities/proposed-changes/stores/proposedChanges.atom";
import { Conversations } from "../../../src/entities/proposed-changes/ui/conversations";
import { nodeSchemasAtom } from "../../../src/entities/schema/stores/schema.atom";
import { accountDetailsMocksSchema } from "../../mocks/data/account";
import {
  conversationMocksData,
  conversationMocksQuery,
  conversationMocksSchema,
  proposedChangesId,
} from "../../mocks/data/conversations";
import { proposedChangesDetails } from "../../mocks/data/proposedChanges";
import { TestProvider } from "../../mocks/jotai/atom";

const url = `/proposed-changes/${proposedChangesId}`;
const path = "/proposed-changes/:proposedChangeId";

// Mock the apollo query and data
const mocks: any[] = [
  {
    request: {
      query: gql`
        ${conversationMocksQuery}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: conversationMocksData,
    },
  },
];

// Provide the initial value for jotai
const ConversationsProvider = () => {
  return (
    <TestProvider
      initialValues={[
        [nodeSchemasAtom, [...conversationMocksSchema, ...accountDetailsMocksSchema]],
        [proposedChangedState, proposedChangesDetails],
      ]}
    >
      <Conversations />
    </TestProvider>
  );
};

describe("List screen", () => {
  it("should display a conversation with comments", () => {
    cy.viewport(1920, 1080);
    cy.fixture("config").then(function (json) {
      cy.intercept("GET", "/api/config", json).as("config");
    });

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ConversationsProvider />} path={path} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [url],
        },
      }
    );

    cy.contains("#1").should("exist");
    cy.contains("#2").should("exist");
    cy.contains("#3").should("exist");
  });
});
