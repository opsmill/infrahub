import { expect, type Mock, vi } from "vitest";
import { page } from "vitest/browser";

// Every property is required so that an unpaired request assertion is a type error, not a review catch.
type ExpectServerDrivenChangeOptions<TVariables extends object, TPayload> = {
  apiMock: Mock<(variables: TVariables) => Promise<TPayload>>;
  callIndex: number;
  variables: TVariables;
  payload: TPayload;
  rowVisibleAfter: string;
};

export async function expectServerDrivenChange<TVariables extends object, TPayload>({
  apiMock,
  callIndex,
  variables,
  payload,
  rowVisibleAfter,
}: ExpectServerDrivenChangeOptions<TVariables, TPayload>): Promise<void> {
  await vi.waitFor(() => {
    expect(apiMock.mock.calls.length).toBeGreaterThan(callIndex);
    expect(apiMock.mock.calls.at(callIndex)?.[0]).toMatchObject(variables);
  });

  // `results` is indexed by invocation, unlike `settledResults`, which fills in settlement order and
  // would pair the variables of one call with the answer of another whenever two are in flight.
  const result = apiMock.mock.results.at(callIndex);

  expect(result?.type).toBe("return");
  await expect(result?.value).resolves.toEqual(payload);

  await expect.element(page.getByRole("row", { name: rowVisibleAfter })).toBeVisible();
}
