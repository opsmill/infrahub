/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { proposedChangedState } from "../../../src/state/atoms/proposedChanges.atom";
import { schemaState } from "../../../src/state/atoms/schema.atom";
import { accountDetailsMocksSchema } from "../../mocks/data/account";
import { proposedChangesId } from "../../mocks/data/conversations";
import { TestProvider } from "../../mocks/jotai/atom";
import { MockedProvider } from "@apollo/client/testing";
import { Route, Routes } from "react-router-dom";
import { withAuth } from "../../../src/decorators/withAuth";
import { DataDiff } from "../../../src/screens/diff/data-diff";
import {
  DataDiffProposedChangesState,
  diffThreadSchema,
  getAllCoreObjectThreadMockData,
  getAllCoreObjectThreadMockQuery,
  getCoreObjectWithoutThreadMockData,
  getCoreObjectThreadMockQuery,
  getCoreObjectThreadMockData,
} from "../../mocks/data/data-changes";

const url = `/proposed-changes/${proposedChangesId}`;
const path = "/proposed-changes/:proposedchange";

const AuthDataDiff = withAuth(DataDiff);

// Provide the initial value for jotai
const DataDiffProvider = ({ loggedIn }: { loggedIn: boolean }) => {
  return (
    <TestProvider
      initialValues={[
        [schemaState, [diffThreadSchema, ...accountDetailsMocksSchema]],
        [proposedChangedState, DataDiffProposedChangesState],
      ]}>
      {loggedIn ? <AuthDataDiff /> : <DataDiff />}
    </TestProvider>
  );
};

describe("Data Diff", () => {
  before(function () {
    cy.viewport(1920, 1080);
  });

  beforeEach(function () {
    cy.fixture("diff-data").then(function (json) {
      cy.intercept("GET", "/api/diff/data*", json).as("diff-data");
    });
  });

  describe("when not logged in", () => {
    it("should display data diff without comments", function () {
      // GIVEN
      const mocks = [
        {
          request: {
            query: gql`
              ${getAllCoreObjectThreadMockQuery}
            `,
          },
          result: {
            data: getCoreObjectWithoutThreadMockData,
          },
        },
        {
          request: {
            query: gql`
              ${getCoreObjectThreadMockQuery}
            `,
          },
          result: {
            data: getCoreObjectWithoutThreadMockData,
          },
        },
      ];

      // WHEN
      cy.mount(
        <MockedProvider mocks={mocks} addTypename={false}>
          <Routes>
            <Route element={<DataDiffProvider loggedIn={false} />} path={path} />
          </Routes>
        </MockedProvider>,
        {
          routerProps: {
            initialEntries: [url],
          },
        }
      );

      // THEN
      cy.get("[data-cy='data-diff']").should("be.visible");
      cy.get("[data-cy='data-diff-add-reply']").should("not.exist");
      cy.get("[data-cy='comments-count']").should("not.exist");
      cy.contains("UPDATED").should("be.visible");
      cy.contains("InfraDevice").should("be.visible");
      cy.contains("atl1-edge1").should("be.visible");
      cy.contains("+0|1|-0").should("be.visible");
    });

    it("should display data diff with threads", function () {
      // GIVEN
      const mocks = [
        {
          request: {
            query: gql`
              ${getAllCoreObjectThreadMockQuery}
            `,
          },
          result: getAllCoreObjectThreadMockData,
        },
        {
          request: {
            query: gql`
              ${getCoreObjectThreadMockQuery}
            `,
          },
          result: getCoreObjectThreadMockData,
        },
      ];

      cy.mount(
        <MockedProvider mocks={mocks} addTypename={false}>
          <Routes>
            <Route element={<DataDiffProvider loggedIn={false} />} path={path} />
          </Routes>
        </MockedProvider>,
        {
          routerProps: {
            initialEntries: [url],
          },
        }
      );
      cy.get("[data-cy='data-diff']").should("be.visible");
      cy.get("[data-cy='data-diff-add-reply']").should("be.visible").and("be.disabled");
      cy.get("[data-cy='comments-count']").should("be.visible");
      cy.contains("UPDATED").should("be.visible");
      cy.contains("InfraDevice").should("be.visible");
      cy.contains("atl1-edge1").should("be.visible");
      cy.contains("+0|1|-0").should("be.visible");

      // WHEN
      cy.get("[data-cy='data-diff-add-reply']").click({ force: true });

      // THEN
      cy.contains("Conversation").should("not.exist");
    });

    it("should not be able to add comments", function () {
      // GIVEN
      const mocks = [
        {
          request: {
            query: gql`
              ${getAllCoreObjectThreadMockQuery}
            `,
          },
          result: {
            data: getCoreObjectWithoutThreadMockData,
          },
        },
        {
          request: {
            query: gql`
              ${getCoreObjectThreadMockQuery}
            `,
          },
          result: {
            data: getCoreObjectWithoutThreadMockData,
          },
        },
      ];
      cy.mount(
        <MockedProvider mocks={mocks} addTypename={false}>
          <Routes>
            <Route element={<DataDiffProvider loggedIn={false} />} path={path} />
          </Routes>
        </MockedProvider>,
        {
          routerProps: {
            initialEntries: [url],
          },
        }
      );

      // WHEN
      cy.get("[data-cy='data-diff-add-comment']").click({ force: true });

      // THEN
      cy.contains("Conversation").should("not.exist");
    });
  });
});
