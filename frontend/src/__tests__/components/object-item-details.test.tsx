import { render, screen } from "@testing-library/react";
import { Params } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { accountDetailsMocksQuery } from "../../../mocks/data/account";
import { schemaMocks } from "../../../mocks/data/schema";
import { TestProvider } from "../../../mocks/jotai/atom";
import ObjectItemDetails from "../../components/tests/object-item-details";
import { schemaState } from "../../state/atoms/schema.atom";
import { cleanTabsAndNewLines } from "../../utils/string";

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
