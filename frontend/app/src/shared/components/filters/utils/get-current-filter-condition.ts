import { Filter } from "@/shared/hooks/useFilters";

export function getCurrentFilterCondition(filter?: Filter) {
  if (!filter) return undefined;

  const condition = filter.name.split("__")[1];

  if (condition === "ids") {
    return "is any of";
  }

  if (condition === "isnull") {
    return filter.value ? "is empty" : "is not empty";
  }
}
