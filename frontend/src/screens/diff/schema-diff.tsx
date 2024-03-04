import { useAtomValue } from "jotai/index";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from "react";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { CONFIG } from "../../config/config";
import { QSP } from "../../config/qsp";
import { proposedChangedState } from "../../state/atoms/proposedChanges.atom";
import { fetchUrl, getUrlWithQsp } from "../../utils/fetch";
import LoadingScreen from "../loading-screen/loading-screen";
import { DataDiffNode } from "./data-diff-node";

export const SchemaDiff = forwardRef((props, ref) => {
  const proposedChangeDetails = useAtomValue(proposedChangedState);
  const [diff, setDiff] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const [timeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);

  const fetchDiffDetails = useCallback(async () => {
    if (!proposedChangeDetails?.source_branch?.value) return;

    setIsLoading(true);

    const url = CONFIG.SCHEMA_DIFF_URL(proposedChangeDetails?.source_branch?.value);

    const options: string[][] = [
      ["branch_only", branchOnly ?? ""],
      ["time_from", timeFrom ?? ""],
      ["time_to", timeTo ?? ""],
    ].filter(([, v]) => v !== undefined && v !== "");

    const urlWithQsp = getUrlWithQsp(url, options);

    try {
      const diffDetails = await fetchUrl(urlWithQsp);

      setDiff(diffDetails?.diffs ?? []);
    } catch (err) {
      console.error("Error when loading branch diff: ", err);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading branch diff" />);
    }

    setIsLoading(false);
  }, [proposedChangeDetails?.source_branch?.value, branchOnly, timeFrom, timeTo]);

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch: fetchDiffDetails }));

  useEffect(() => {
    fetchDiffDetails();
  }, [fetchDiffDetails]);

  return (
    <>
      {isLoading && <LoadingScreen />}

      {!isLoading && (
        <div>
          {diff?.map((node: any, index: number) => (
            <DataDiffNode key={index} node={node} />
          ))}
        </div>
      )}
    </>
  );
});
