/// <reference types="cypress" />

import { MockedProvider } from "@apollo/client/testing";
import { AccountMenu } from "../../../src/components/account-menu";
import { ACCESS_TOKEN_KEY } from "../../../src/config/localStorage";
import { AuthProvider } from "../../../src/hooks/useAuth";
import { genericsState } from "../../../src/state/atoms/schema.atom";
import { encodeJwt } from "../../../src/utils/common";
import { accountDetailsMocksSchema } from "../../mocks/data/account";
import {
  profileDetailsMocksData,
  profileDetailsMocksQuery,
  profileId,
} from "../../mocks/data/account-profile";
import { TestProvider } from "../../mocks/jotai/atom";

// Mock the apollo query and data
const mocks = [
  {
    request: {
      query: profileDetailsMocksQuery,
      variables: {},
    },
    result: {
      data: profileDetailsMocksData,
    },
  },
];

const AuthHeader = () => (
  <AuthProvider>
    <AccountMenu />
  </AuthProvider>
);

describe("List screen", () => {
  it("should fetch items and render list", () => {
    cy.viewport(1920, 1080);

    const data = {
      sub: profileId,
    };

    const token = encodeJwt(data);

    localStorage.setItem(ACCESS_TOKEN_KEY, token);

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <TestProvider initialValues={[[genericsState, accountDetailsMocksSchema]]}>
          <AuthHeader />
        </TestProvider>
      </MockedProvider>
    );

    cy.contains(profileDetailsMocksData.AccountProfile.display_label);
  });
});
