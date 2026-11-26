import { useQueryState } from "nuqs";
import * as R from "remeda";

import { QSP } from "@/shared/config/qsp";

import type {
  NumberPoolDivisionSelector,
  NumberPoolDivisionValue,
} from "@/entities/resource-manager/domain/model/number-pool";

export type NumberPoolDivisionInvalidCause =
  | { reason: "unreadable" }
  | { reason: "count"; count: number };

export type NumberPoolDivisionState =
  | { status: "none" }
  | { status: "invalid"; cause: NumberPoolDivisionInvalidCause }
  | { status: "selected"; selector: NumberPoolDivisionSelector };

const isDivisionValue = (value: unknown): value is NumberPoolDivisionValue =>
  typeof value === "string" || typeof value === "number" || typeof value === "boolean";

const parseDivisionValues = (raw: string): NumberPoolDivisionValue[] | null => {
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.every(isDivisionValue) ? parsed : null;
  } catch {
    return null;
  }
};

export function useNumberPoolDivision(fields: string[]): NumberPoolDivisionState {
  const [raw] = useQueryState(QSP.ALLOCATION_SCOPE);

  if (raw === null) return { status: "none" };

  const values = parseDivisionValues(raw);
  if (!values) return { status: "invalid", cause: { reason: "unreadable" } };
  if (values.length !== fields.length) {
    return { status: "invalid", cause: { reason: "count", count: values.length } };
  }

  return {
    status: "selected",
    selector: R.zip(fields, values).map(([path, value]) => ({ path, value })),
  };
}
