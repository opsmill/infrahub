import { QueryClientProvider } from "@tanstack/react-query";
import { MountOptions, MountReturn } from "cypress/react";
import { mount } from "cypress/react";
import queryString from "query-string";
import React from "react";
import { MemoryRouter, MemoryRouterProps } from "react-router";
import { QueryParamProvider } from "use-query-params";

import "../../src/app/styles/index.css";
import { queryClient } from "../../src/shared/api/rest/client";
import { ReactRouter7Adapter } from "../../src/shared/libs/use-query-params";

import "./commands";

// Augment the Cypress namespace to include type definitions for
// your custom command.
// Alternatively, can be defined in cypress/support/component.d.ts
// with a <reference path="./component" /> at the top of your spec.
declare global {
  namespace Cypress {
    interface Chainable {
      /**
       * Mounts a React node
       * @param component React Node to mount
       * @param options Additional options to pass into mount
       */
      mount(
        component: React.ReactNode,
        options?: MountOptions & { routerProps?: MemoryRouterProps }
      ): Cypress.Chainable<MountReturn>;
    }
  }
}

Cypress.Commands.add("mount", (component, options = {}) => {
  const { routerProps = { initialEntries: ["/"] }, ...mountOptions } = options;

  const wrapped = (
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter {...routerProps} basename="/">
          <QueryParamProvider
            adapter={ReactRouter7Adapter}
            options={{
              searchStringToObject: queryString.parse,
              objectToSearchString: queryString.stringify,
            }}
          >
            {component}
          </QueryParamProvider>
        </MemoryRouter>
      </QueryClientProvider>
    </React.StrictMode>
  );

  return mount(wrapped, mountOptions);
});
