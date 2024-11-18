/// <reference types="cypress" />

import { MockedProvider } from "@apollo/client/testing";
import { Route, Routes } from "react-router-dom";
import { schemaState } from "../../../src/state/atoms/schema.atom";

import { gql } from "@apollo/client";
import { ACCESS_TOKEN_KEY } from "../../../src/config/localStorage";
import { AuthProvider } from "../../../src/hooks/useAuth";
import { encodeJwt } from "../../../src/utils/common";
import { accountDetailsMocksSchema } from "../../mocks/data/account";
import {
  profileDetailsMocksData,
  profileId,
  profilesDetailsMocksQuery,
} from "../../mocks/data/account-profile";
import {
  taskMocksData as taskMocksData1,
  taskMocksQuery as taskMocksQuery1,
  taskMocksSchema as taskMocksSchema1,
  taskMocksSchemaOptional as taskMocksSchemaOptionnal1,
  taskMocksSchemaWithProfile,
} from "../../mocks/data/task_1";
import {
  taskMocksData as taskMocksData2,
  taskMocksQuery as taskMocksQuery2,
  taskMocksSchema as taskMocksSchema2,
  taskMocksSchemaOptional as taskMocksSchemaOptional2,
  taskMocksSchemaWithDefaultValue as taskMocksSchemaWithDefaultValue2,
} from "../../mocks/data/task_2";
import {
  taskMocksData as taskMocksData3,
  taskMocksQuery as taskMocksQuery3,
  taskMocksSchema as taskMocksSchema3,
  taskMocksSchemaOptional as taskMocksSchemaOptional3,
  taskMocksSchemaWithDefaultValue as taskMocksSchemaWithDefaultValue3,
} from "../../mocks/data/task_3";
import {
  taskMocksData as taskMocksData4,
  taskMocksQuery as taskMocksQuery4,
  taskMocksSchema as taskMocksSchema4,
} from "../../mocks/data/task_4";
import {
  taskMocksData as taskMocksData5,
  taskMocksQuery as taskMocksQuery5,
  taskMocksSchema as taskMocksSchema5,
} from "../../mocks/data/task_5";

import { ObjectItemsPage } from "../../../src/pages/objects/object-items";
import { ipamIpAddressMocksSchema } from "../../mocks/data/ip-address";
import { ipPrefixMocksSchema } from "../../mocks/data/ip-prefix";
import { numberPoolData, numberPoolQuery } from "../../mocks/data/number-pool";
import {
  taskMocksData as taskMocksData6,
  taskMocksQuery as taskMocksQuery6,
  taskMocksSchema as taskMocksSchema6,
} from "../../mocks/data/task_6";
import {
  taskMocksData as taskMocksData7,
  taskMocksQuery as taskMocksQuery7,
  taskMocksSchema as taskMocksSchema7,
} from "../../mocks/data/task_7";
import { TestProvider } from "../../mocks/jotai/atom";

// URL for the current view
const mockedUrl = "/objects/TestTask";

// Path that will match the route to display the component
const mockedPath = "/objects/:objectKind";

// Mock the apollo query and data
const mocks: any[] = [
  {
    request: {
      query: gql`
        ${profilesDetailsMocksQuery}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: profileDetailsMocksData,
    },
  },
  {
    request: {
      query: gql`
        ${taskMocksQuery1}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: taskMocksData1,
    },
  },
  {
    request: {
      query: gql`
        ${taskMocksQuery2}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: taskMocksData2,
    },
  },
  {
    request: {
      query: gql`
        ${taskMocksQuery3}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: taskMocksData3,
    },
  },
  {
    request: {
      query: gql`
        ${taskMocksQuery4}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: taskMocksData4,
    },
  },
  {
    request: {
      query: gql`
        ${taskMocksQuery5}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: taskMocksData5,
    },
  },
  {
    request: {
      query: gql`
        ${taskMocksQuery6}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: taskMocksData6,
    },
  },
  {
    request: {
      query: gql`
        ${taskMocksQuery7}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: taskMocksData7,
    },
  },
  {
    request: {
      query: numberPoolQuery,
    },
    result: numberPoolData,
  },
];

const AuthenticatedObjectItems = () => (
  <AuthProvider>
    <ObjectItemsPage />
  </AuthProvider>
);

describe("Object list", () => {
  beforeEach(function () {
    const data = {
      sub: profileId,
      user_claims: {
        role: "admin",
      },
    };

    const token = encodeJwt(data);

    localStorage.setItem(ACCESS_TOKEN_KEY, token);
  });

  it("should open the add panel, submit without filling the text field and display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[[schemaState, [...accountDetailsMocksSchema, ...taskMocksSchema1]]]}
        >
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get("[data-cy='submit-form']").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("have.text", "Required");
  });

  it("should open the add panel, submit without filling the text field (with profile) and display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[
            [schemaState, [...accountDetailsMocksSchema, ...taskMocksSchemaWithProfile]],
          ]}
        >
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get("[data-cy='submit-form']").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("have.text", "Required");
  });

  it("should open the add panel, submit after filling the text field and do not display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[
            [schemaState, [...accountDetailsMocksSchema, ...taskMocksSchemaOptionnal1]],
          ]}
        >
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get("[data-cy='submit-form']").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without checking the checkbox and do not display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[[schemaState, [...accountDetailsMocksSchema, ...taskMocksSchema2]]]}
        >
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get("[data-cy='submit-form']").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without checking the checkbox and should not display a required message (default value is defined)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[
            [schemaState, [...accountDetailsMocksSchema, ...taskMocksSchemaWithDefaultValue2]],
          ]}
        >
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get("[data-cy='submit-form']").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without checking the checkbox and should not display a required message (optional)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[
            [schemaState, [...accountDetailsMocksSchema, ...taskMocksSchemaOptional2]],
          ]}
        >
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get("[data-cy='submit-form']").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without defining an integer and display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[[schemaState, [...accountDetailsMocksSchema, ...taskMocksSchema3]]]}
        >
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get("[data-cy='submit-form']").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("have.text", "Required");
  });

  it("should open the add panel, submit without defining an integer and should not display a required message (0 should work as defined integer)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[[schemaState, [...accountDetailsMocksSchema, ...taskMocksSchema3]]]}
        >
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Type 0 as value
    cy.get("[name='counter']").type("0", { delay: 0, force: true });

    // Save
    cy.get("[data-cy='submit-form']").click();

    // The required message should not appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without defining an integer and should not display a required message (default value is defined)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[
            [schemaState, [...accountDetailsMocksSchema, ...taskMocksSchemaWithDefaultValue3]],
          ]}
        >
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get("[data-cy='submit-form']").click();

    // The required message should not appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without defining an integer and should not display a required message (optional)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[
            [schemaState, [...accountDetailsMocksSchema, ...taskMocksSchemaOptional3]],
          ]}
        >
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get("[data-cy='submit-form']").click();

    // The required message should not appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without defining a datetime and should display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[[schemaState, [...accountDetailsMocksSchema, ...taskMocksSchema4]]]}
        >
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get("[data-cy='submit-form']").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("have.text", "Required");
  });

  it("should open the add panel, submit without defining a multiselect relationships and should display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[[schemaState, [...accountDetailsMocksSchema, ...taskMocksSchema5]]]}
        >
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get("[data-cy='submit-form']").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("have.text", "Required");
  });

  it("should open the add panel, and display the pool button for multiselect", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[
            [
              schemaState,
              [
                ...accountDetailsMocksSchema,
                ...taskMocksSchema6,
                ipPrefixMocksSchema,
                ipamIpAddressMocksSchema,
              ],
            ],
          ]}
        >
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // eslint-disable-next-line quotes
    cy.get('[data-testid="select-open-pool-option-button"]').should("be.visible");
  });

  it("should open the add panel, and display the description", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");
    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[[schemaState, [...accountDetailsMocksSchema, ...taskMocksSchema7]]]}
        >
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };
    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );
    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Check description question mark
    cy.get("[data-cy='question-mark']").should("be.visible");
  });
});
