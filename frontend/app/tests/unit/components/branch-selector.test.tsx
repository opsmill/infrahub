import { act, cleanup, render, screen } from "@testing-library/react";
import queryString from "query-string";
import { BrowserRouter } from "react-router-dom";
import { QueryParamProvider } from "use-query-params";
import { ReactRouter6Adapter } from "use-query-params/adapters/react-router-6";
import { afterAll, describe, expect, it } from "vitest";
import { QSP } from "../../../src/config/qsp";
import BranchSelector from "./branch-selector";

afterAll(cleanup);

describe("Branch selector", () => {
  it("should get the branch from the URL", async () => {
    render(
      <BrowserRouter basename="/">
        <QueryParamProvider
          adapter={ReactRouter6Adapter}
          options={{
            searchStringToObject: queryString.parse,
            objectToSearchString: queryString.stringify,
          }}>
          <BranchSelector />
        </QueryParamProvider>
      </BrowserRouter>
    );

    expect(window.location.search).toEqual("");

    expect(await screen.findByText("main")).toBeTruthy();

    act(() => {
      screen.getByText(/Click me/).click();
    });

    expect(window.location.search).toEqual(`?${QSP.BRANCH}=test`);

    expect(await screen.findByText("test")).toBeTruthy();
  });
});
