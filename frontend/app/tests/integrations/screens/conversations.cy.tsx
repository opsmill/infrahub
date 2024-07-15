/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import React from "react";
import { Route, Routes } from "react-router-dom";
import { Conversations } from "../../../src/screens/proposed-changes/conversations";
import { proposedChangedState } from "../../../src/state/atoms/proposedChanges.atom";
import { schemaState } from "../../../src/state/atoms/schema.atom";
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
const path = "/proposed-changes/:proposedchange";

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
        [schemaState, [...conversationMocksSchema, ...accountDetailsMocksSchema]],
        [proposedChangedState, proposedChangesDetails],
      ]}>
      <Conversations />
    </TestProvider>
  );
};

describe("List screen", () => {
  it("should display a conversation with comments", () => {
    cy.viewport(1920, 1080);

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
