import { render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import { useHydrateAtoms } from "jotai/utils";
import { Params } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { accountDetailsMocks } from "../../../mocks/object-item-details";
import { schemaMocks } from "../../../mocks/schema";
import ObjectItemDetails from "../../components/tests/object-item-details";
import { schemaState } from "../../state/atoms/schema.atom";
import { cleanTabsAndNewLines } from "../../utils/string";

vi.mock("react-router-dom", () => ({
  useParams: (): Readonly<Params<string>> => ({ objectname: "account", objectid: "1234" }),
}));

const HydrateAtoms = ({ initialValues, children }: any) => {
  useHydrateAtoms(initialValues);
  return children;
};

const TestProvider = ({ initialValues, children }: any) => (
  <Provider>
    <HydrateAtoms initialValues={initialValues}>{children}</HydrateAtoms>
  </Provider>
);

const ObjectItemDetailsProvider = () => {
  return (
    <TestProvider initialValues={[[schemaState, schemaMocks]]}>
      <ObjectItemDetails />
    </TestProvider>
  );
};

describe("Object item details", () => {
  it("should compute a correct query", () => {
    render(<ObjectItemDetailsProvider />);

    const query = screen.getByText(/Query:.*/);

    expect(query.textContent).toContain(cleanTabsAndNewLines(accountDetailsMocks));
  });
});
