import { describe, expect, it } from "vitest";

import { getLastErrorLine } from "@/entities/repository/domain/rules/get-last-error-line";

const log = (severity: string, message: string) => ({ severity, message });

describe("getLastErrorLine", () => {
  it("returns null when there are no logs", () => {
    expect(getLastErrorLine([])).toBeNull();
  });

  it("returns null when no line is an error", () => {
    expect(getLastErrorLine([log("info", "Starting"), log("warning", "Slow clone")])).toBeNull();
  });

  it("picks the last error or critical line, ignoring info and warning after it", () => {
    const logs = [
      log("error", "first error"),
      log("critical", "schema load failed"),
      log("info", "cleaning up"),
      log("warning", "retrying"),
    ];

    expect(getLastErrorLine(logs)).toBe("schema load failed");
  });

  it("matches severities in any case", () => {
    expect(getLastErrorLine([log("ERROR", "upper"), log("Critical", "mixed")])).toBe("mixed");
  });

  it("keeps inner newlines and trims trailing whitespace", () => {
    expect(getLastErrorLine([log("error", "line one\n  line two\n\n  \t")])).toBe(
      "line one\n  line two"
    );
  });

  it("returns a non-wrapper error line verbatim", () => {
    const message = "Unable to load the schema: invalid .infrahub.yml at line 3";

    expect(getLastErrorLine([log("error", message)])).toBe(message);
  });

  it("unwraps Prefect's final-state wrapper to the exception", () => {
    const logs = [
      log("error", "Encountered exception during execution: RepositoryError('bad config')"),
      log(
        "error",
        "Finished in state Failed('Flow run encountered an exception: RepositoryError: bad config')"
      ),
    ];

    expect(getLastErrorLine(logs)).toBe("RepositoryError: bad config");
  });

  it("unescapes quotes and newlines inside the wrapper", () => {
    const message = String.raw`Finished in state Failed("Flow run encountered an exception: ValidationError: field 'name' is required\nat line 2")`;

    expect(getLastErrorLine([log("error", message)])).toBe(
      "ValidationError: field 'name' is required\nat line 2"
    );
  });

  it("unescapes both quote kinds when Python escaped them", () => {
    const message = String.raw`Finished in state Failed('Flow run encountered an exception: Error: it\'s "bad"')`;

    expect(getLastErrorLine([log("error", message)])).toBe(`Error: it's "bad"`);
  });

  it("unwraps a final state without the exception prefix", () => {
    expect(
      getLastErrorLine([log("error", "Finished in state Crashed('Execution was cancelled')")])
    ).toBe("Execution was cancelled");
  });

  it("unwraps a final state that names its type", () => {
    const message =
      "Finished in state TimedOut('Flow run encountered an exception: TimeoutError: clone took too long', type=FAILED)";

    expect(getLastErrorLine([log("error", message)])).toBe("TimeoutError: clone took too long");
  });

  it("returns the wrapper as is when unwrapping yields nothing", () => {
    const message = "Finished in state Failed('Flow run encountered an exception: ')";

    expect(getLastErrorLine([log("error", message)])).toBe(message);
  });
});
