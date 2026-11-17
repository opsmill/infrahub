export interface ImportLogLine {
  message: string;
  severity: string;
}

const ERROR_SEVERITIES = new Set(["error", "critical"]);

// Prefect logs a failed run's end as `Finished in state <State>(<repr of the state message>)`,
// with an optional `, type=<TYPE>` when the state name differs from its type.
const PREFECT_FINAL_STATE = /^Finished in state \w+\((['"])(.*)\1(?:, type=\w+)?\)$/s;
const PREFECT_EXCEPTION_PREFIX = "Flow run encountered an exception: ";

const PYTHON_SIMPLE_ESCAPES: Record<string, string> = {
  "\\": "\\",
  "'": "'",
  '"': '"',
  n: "\n",
  r: "\r",
  t: "\t",
};

function unescapePythonRepr(value: string): string {
  return value.replace(
    /\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|.)/gs,
    (escapeSequence, sequence: string) => {
      if (sequence.length > 1) {
        return String.fromCodePoint(Number.parseInt(sequence.slice(1), 16));
      }
      return PYTHON_SIMPLE_ESCAPES[sequence] ?? escapeSequence;
    }
  );
}

function unwrapPrefectFinalState(line: string): string {
  const quoted = PREFECT_FINAL_STATE.exec(line)?.[2];
  if (quoted === undefined) return line;

  const stateMessage = unescapePythonRepr(quoted);
  const cause = stateMessage.startsWith(PREFECT_EXCEPTION_PREFIX)
    ? stateMessage.slice(PREFECT_EXCEPTION_PREFIX.length)
    : stateMessage;

  return cause.trim() ? cause.trimEnd() : line;
}

export function getLastErrorLine(logs: ReadonlyArray<ImportLogLine>): string | null {
  const lastError = logs
    .filter(({ severity }) => ERROR_SEVERITIES.has(severity.toLowerCase()))
    .at(-1);
  if (!lastError) return null;

  return unwrapPrefectFinalState(lastError.message.trimEnd());
}
