import { getObjectsCount } from "@/entities/nodes/object/domain/use-cases/get-objects-count";
import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_ERROR_IMPORT_FILTER,
} from "@/entities/repository/domain/model/repository";

export type RepositorySyncHealth = "none" | "failing" | "in-sync";

export type GetRepositorySyncHealth = (branch: string) => Promise<RepositorySyncHealth>;

export const getRepositorySyncHealth: GetRepositorySyncHealth = async (branch: string) => {
  // `atDate: null` reports current state, whatever time frame the page is showing.
  const context = { objectKind: GENERIC_REPOSITORY_KIND, branchName: branch, atDate: null };

  const total = await getObjectsCount(context);
  if (total === 0) return "none";

  const failing = await getObjectsCount({ ...context, filters: [REPOSITORY_ERROR_IMPORT_FILTER] });

  return failing > 0 ? "failing" : "in-sync";
};
