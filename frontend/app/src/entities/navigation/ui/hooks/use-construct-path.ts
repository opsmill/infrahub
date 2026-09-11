import { useAtomValue } from "jotai";

import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

/**
 * Builds in-app paths that carry the active branch and the time-machine date.
 *
 * Both are read from their in-app owners rather than from the URL. A render-time read of
 * `window.location` is cached by React Compiler once per mount, so a link rendered by a component
 * that outlives a branch switch — the sidebar, the header, breadcrumbs — would keep pointing at the
 * branch that was active when it first rendered. nuqs also writes the branch with `shallow: true`,
 * which leaves the URL a tick behind and invisible to the router's own location.
 */
export function useConstructPath() {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);

  // Absence of the branch param *is* the default branch, so the default branch excludes it.
  const ambientParams: overrideQueryParams[] = [
    currentBranch.is_default
      ? { name: QSP.BRANCH, exclude: true }
      : { name: QSP.BRANCH, value: currentBranch.name },
    ...(atDate ? [{ name: QSP.DATETIME, value: atDate.toISOString() }] : []),
  ];

  // Caller overrides come last so a link deliberately targeting another branch still wins.
  return (path: string, overrideParams: overrideQueryParams[] = [], preserveQspLib?: string[]) =>
    constructPath(path, [...ambientParams, ...overrideParams], preserveQspLib);
}
