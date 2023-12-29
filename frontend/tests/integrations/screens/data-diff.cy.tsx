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
  objectThreadSchema,
  getAllCoreObjectThreadMockData,
  getAllCoreObjectThreadMockQuery,
  getCoreObjectWithoutThreadMockData,
  getCoreObjectThreadMockQuery,
  getCoreObjectThreadMockData,
  getProposedChangesCommentsMockQuery,
  createThreadMockData,
  getProposedChangesCommentsMockData,
} from "../../mocks/data/data-changes";
import { profileId } from "../../mocks/data/profile";
import { encodeJwt } from "../../../src/utils/common";
import { ACCESS_TOKEN_KEY } from "../../../src/config/constants";
import graphqlClient from "../../../src/graphql/graphqlClientApollo";

const url = `/proposed-changes/${proposedChangesId}`;
const path = "/proposed-changes/:proposedchange";

const mocksWithComments = [
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

const mocksWithoutComments = [
  {
    request: {
      query: gql`
        ${getAllCoreObjectThreadMockQuery}
      `,
    },
    result: getCoreObjectWithoutThreadMockData,
  },
  {
    request: {
      query: gql`
        ${getCoreObjectThreadMockQuery}
      `,
    },
    result: getCoreObjectWithoutThreadMockData,
  },
];

const AuthDataDiff = withAuth(DataDiff);

// Provide the initial value for jotai
const DataDiffProvider = ({ loggedIn }: { loggedIn: boolean }) => {
  return (
    <TestProvider
      initialValues={[
        [schemaState, [objectThreadSchema, ...accountDetailsMocksSchema]],
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
      cy.mount(
        <MockedProvider mocks={mocksWithoutComments} addTypename={false}>
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

      cy.mount(
        <MockedProvider mocks={mocksWithComments} addTypename={false}>
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
      cy.mount(
        <MockedProvider mocks={mocksWithoutComments} addTypename={false}>
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

  describe("when logged in", () => {
    beforeEach(() => {
      const data = {
        sub: profileId,
        user_claims: {
          role: "admin",
        },
      };

      const token = encodeJwt(data);

      localStorage.setItem(ACCESS_TOKEN_KEY, token);
    });

    after(() => {
      localStorage.clear();
    });

    it("should display data diff and be able to add first comment", function () {
      // GIVEN
      const mockConversationWithoutComment = [
        {
          request: {
            query: gql`
              ${getProposedChangesCommentsMockQuery}
            `,
          },
          result: getCoreObjectWithoutThreadMockData,
        },
      ];
      cy.stub(graphqlClient, "mutate").returns(createThreadMockData);
      cy.mount(
        <MockedProvider
          mocks={[...mocksWithoutComments, ...mockConversationWithoutComment]}
          addTypename={false}>
          <Routes>
            <Route element={<DataDiffProvider loggedIn />} path={path} />
          </Routes>
        </MockedProvider>,
        {
          routerProps: {
            initialEntries: [url],
          },
        }
      );
      cy.get("[data-cy='data-diff']").should("be.visible");
      cy.get("[data-cy='data-diff-add-reply']").should("not.exist");
      cy.get("[data-cy='comments-count']").should("not.exist");
      cy.contains("UPDATED").should("be.visible");
      cy.contains("InfraDevice").should("be.visible");
      cy.contains("atl1-edge1").should("be.visible");
      cy.contains("+0|1|-0").should("be.visible");

      // WHEN
      cy.get("[data-cy='data-diff-add-comment']").click({ force: true }); // Impossible de trigger hover with cypress, so force: true needed

      // THEN
      cy.contains("Conversation").should("exist");
      const REPLY = "new comment";
      cy.get("[data-cy='codemirror-editor']").first().type(REPLY);
      cy.intercept("/graphql/main*", { middleware: true }, (req) => {
        if (req.body.query.includes("CoreThreadComment")) {
          expect(req.body.query).to.contains(REPLY);
        }
      });
      cy.contains("button", "Comment").click();
    });

    it("should display data diff and its threads", function () {
      // GIVEN
      const mockConversationWithComment = [
        {
          request: {
            query: gql`
              ${getProposedChangesCommentsMockQuery}
            `,
          },
          result: getProposedChangesCommentsMockData,
        },
      ];
      cy.stub(graphqlClient, "mutate").returns({ data: { ok: true } });
      cy.mount(
        <MockedProvider
          mocks={[...mocksWithComments, ...mockConversationWithComment]}
          addTypename={false}>
          <Routes>
            <Route element={<DataDiffProvider loggedIn />} path={path} />
          </Routes>
        </MockedProvider>,
        {
          routerProps: {
            initialEntries: [url],
          },
        }
      );
      cy.get("[data-cy='data-diff']").should("be.visible");
      cy.get("[data-cy='data-diff-add-reply']").should("be.visible").and("be.enabled");
      cy.get("[data-cy='comments-count']").should("be.visible");
      cy.contains("UPDATED").should("be.visible");
      cy.contains("InfraDevice").should("be.visible");
      cy.contains("atl1-edge1").should("be.visible");
      cy.contains("+0|1|-0").should("be.visible");

      // WHEN
      cy.get("[data-cy='data-diff-add-reply']").click();

      // THEN
      cy.contains("Conversation").should("exist");
      cy.get("[data-cy='thread']").should("be.visible");
      cy.get("[data-cy='thread']").contains("new comment").should("be.visible");
      cy.contains("button", "Reply").click();
      cy.get("[data-cy='codemirror-editor']").first().type("new reply");
      cy.intercept("/graphql/main*", { middleware: true }, (req) => {
        expect(req.body.query).to.contains("new reply");
      });
      cy.contains("button", "Comment").click();
    });
  });
});
