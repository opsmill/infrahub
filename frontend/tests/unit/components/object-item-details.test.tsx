import { render, screen } from "@testing-library/react";
import { Params } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import ObjectItemDetails from "../../../src/components/tests/object-item-details";
import { schemaState } from "../../../src/state/atoms/schema.atom";
import { cleanTabsAndNewLines } from "../../../src/utils/string";
import { accountDetailsMocksQuery } from "../../../tests/mocks/data/account";
import { schemaMocks } from "../../../tests/mocks/data/schema";
import { TestProvider } from "../../../tests/mocks/jotai/atom";

vi.mock("react-router-dom", () => ({
  useParams: (): Readonly<Params<string>> => ({ objectname: "account", objectid: "1234" }),
}));

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

    expect(query.textContent).toContain(cleanTabsAndNewLines(accountDetailsMocksQuery));
  });
});
