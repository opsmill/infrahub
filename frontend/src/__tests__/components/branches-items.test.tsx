import "@testing-library/jest-dom";
import {cleanup, render} from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { BranchesItems } from "../../screens/branches/branches-items";

afterEach(cleanup);

describe("Branches component", () => {
  // const history = createMemoryHistory({ initialEntries: ['/home'] });
  // expect(history.location.pathname).toBe('/home');

  it("should create a button component", () => {
    render(
      <BranchesItems/>,
      { wrapper: BrowserRouter }
    );
  });
});