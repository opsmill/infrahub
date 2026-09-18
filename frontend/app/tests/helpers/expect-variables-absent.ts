import { expect, type Mock } from "vitest";

type ExpectVariablesAbsentOptions<TVariables extends object, TResult> = {
  apiMock: Mock<(variables: TVariables) => TResult>;
  names: readonly string[];
};

// The pairing rule keeps `mock.calls` out of the card's test files, and this absence assertion is
// the one thing `expectServerDrivenChange` cannot express: it matches variables partially.
export function expectVariablesAbsent<TVariables extends object, TResult>({
  apiMock,
  names,
}: ExpectVariablesAbsentOptions<TVariables, TResult>): void {
  expect(apiMock.mock.calls.length).toBeGreaterThan(0);

  for (const [variables] of apiMock.mock.calls) {
    for (const name of names) {
      expect(Object.keys(variables)).not.toContain(name);
    }
  }
}
