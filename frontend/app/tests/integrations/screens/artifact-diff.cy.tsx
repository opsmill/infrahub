/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import { Route, Routes } from "react-router-dom";
import { ACCESS_TOKEN_KEY } from "../../../src/config/constants";
import { withSchemaContext } from "../../../src/decorators/withSchemaContext";
import { AuthProvider } from "../../../src/hooks/useAuth";
import { ArtifactsDiff } from "../../../src/screens/diff/artifact-diff/artifacts-diff";
import { proposedChangedState } from "../../../src/state/atoms/proposedChanges.atom";
import { schemaState } from "../../../src/state/atoms/schema.atom";
import { encodeJwt } from "../../../src/utils/common";
import { accountDetailsMocksSchema } from "../../mocks/data/account";
import {
  artifactThreadMockData,
  artifactThreadMockQuery,
  artifactThreadSchema,
  artifactWithoutThreadMockData,
} from "../../mocks/data/artifact";
import { proposedChangesId } from "../../mocks/data/conversations";

import { profileId } from "../../mocks/data/account-profile";
import { proposedChangesDetails } from "../../mocks/data/proposedChanges";
import { TestProvider } from "../../mocks/jotai/atom";

const url = `/proposed-changes/${proposedChangesId}&pr_tab=artifacts`;
const path = "/proposed-changes/:proposedChangeId";

// Mock the apollo query and data
const mocks = [
  {
    request: {
      query: gql`
        ${artifactThreadMockQuery}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: artifactThreadMockData,
    },
  },
];

const SchemaArtifactsDiff = withSchemaContext(ArtifactsDiff);
const AuthArtifactsDiff = () => (
  <AuthProvider>
    <SchemaArtifactsDiff />
  </AuthProvider>
);

// Provide the initial value for jotai
const ArtifactsDiffProvider = ({ loggedIn }: { loggedIn: boolean }) => {
  return (
    <TestProvider
      initialValues={[
        [schemaState, [...artifactThreadSchema, ...accountDetailsMocksSchema]],
        [proposedChangedState, proposedChangesDetails],
      ]}>
      {loggedIn ? <AuthArtifactsDiff /> : <SchemaArtifactsDiff />}
    </TestProvider>
  );
};

describe("Artifact Diff", () => {
  before(function () {
    cy.viewport(1920, 1080);
    cy.fixture("storage-old").as("storageOld");
    cy.fixture("storage-new").as("storageNew");
  });

  beforeEach(function () {
    cy.fixture("artifacts").then(function (json) {
      cy.intercept("GET", "/api/diff/artifacts*", json).as("artifacts");
    });
    cy.fixture("storage-old").then(function (json) {
      cy.intercept("GET", "api/storage/object/17a28f63-f0bb-b131-3875-c51eff1b7a20", {
        statusCode: 200,
        body: JSON.stringify(json, null, 4),
      }).as("storageOld");
    });
    cy.fixture("storage-new").then(function (json) {
      cy.intercept("GET", "api/storage/object/17a28ff2-526c-2f68-3876-c511fd22b9e3", {
        statusCode: 200,
        body: JSON.stringify(json, null, 4),
      }).as("storageNew");
    });
  });

  it("should display artifact diff", function () {
    // GIVEN
    const mocks = [
      {
        request: {
          query: gql`
            ${artifactThreadMockQuery}
          `,
          variables: { offset: 0, limit: 10 },
        },
        result: {
          data: artifactWithoutThreadMockData,
        },
      },
    ];
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ArtifactsDiffProvider loggedIn={false} />} path={path} />
        </Routes>
      </MockedProvider>,
      {
        routerProps: {
          initialEntries: [url],
        },
      }
    );

    // WHEN
    cy.contains("dfw1-edge1 - test").click();

    // THEN
    cy.contains("Storage id: 17a28f63-f0bb-b131-3875-c51eff1b7a20").should("be.visible");
    cy.contains("Storage id: 17a28ff2-526c-2f68-3876-c511fd22b9e3").should("be.visible");
    cy.get("[data-cy='artifact-content-diff']").should("be.visible");
    cy.get("[data-cy='thread']").should("have.length", 0);
  });

  it("should display artifact diff with threads", function () {
    // GIVEN
    const mocks = [
      {
        request: {
          query: gql`
            ${artifactThreadMockQuery}
          `,
          variables: { offset: 0, limit: 10 },
        },
        result: {
          data: artifactThreadMockData,
        },
      },
    ];
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ArtifactsDiffProvider loggedIn={false} />} path={path} />
        </Routes>
      </MockedProvider>,
      {
        routerProps: {
          initialEntries: [url],
        },
      }
    );

    // WHEN
    cy.contains("dfw1-edge1 - test").click();

    // THEN
    cy.contains("Storage id: 17a28f63-f0bb-b131-3875-c51eff1b7a20").should("be.visible");
    cy.contains("Storage id: 17a28ff2-526c-2f68-3876-c511fd22b9e3").should("be.visible");
    cy.get("[data-cy='artifact-content-diff']").should("be.visible");
    cy.get("[data-cy='thread']").should("have.length", 2);
    cy.contains("comment on new line").should("be.visible");
    cy.contains("comment on old line").should("be.visible");
  });

  describe("when logged in", () => {
    before(() => {
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

    it("should display artifact diff with threads", function () {
      // GIVEN
      cy.mount(
        <MockedProvider mocks={mocks} addTypename={false}>
          <Routes>
            <Route element={<ArtifactsDiffProvider loggedIn />} path={path} />
          </Routes>
        </MockedProvider>,
        {
          routerProps: {
            initialEntries: [url],
          },
        }
      );
      cy.contains("dfw1-edge1 - test").click();
      cy.get("[data-cy='artifact-content-diff']").should("be.visible");
      cy.get("[data-cy='thread']").should("have.length", 2);

      // WHEN
      cy.contains("button", "Reply").click();

      // THEN
      const REPLY = "reply on new line";
      cy.get("[data-cy='codemirror-editor']").first().type(REPLY);
      cy.intercept("/graphql/main*", { middleware: true }, (req) => {
        expect(req.body.query).to.contains(REPLY);
      });
      cy.contains("button", "Comment").click();
    });
  });
});
