import { useAtom } from "jotai";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from "react";
import "react-diff-view/style/index.css";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { CONFIG } from "../../../config/config";
import { QSP } from "../../../config/qsp";
import { proposedChangedState } from "../../../state/atoms/proposedChanges.atom";
import { fetchUrl, getUrlWithQsp } from "../../../utils/fetch";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import NoDataFound from "../../no-data-found/no-data-found";
import { FileRepoDiff } from "./file-repo-diff";

export const FilesDiff = forwardRef((props, ref) => {
  const [filesDiff, setFilesDiff] = useState({});
  const { branchname } = useParams();
  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const [timeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(false);
  const [proposedChangesDetails] = useAtom(proposedChangedState);

  const fetchFiles = useCallback(async () => {
    const branch = branchname || proposedChangesDetails?.source_branch?.value;

    if (!branch) return;

    setIsLoading(true);

    const url = CONFIG.FILES_DIFF_URL(branch);

    const options: string[][] = [
      ["branch_only", branchOnly ?? ""],
      ["time_from", timeFrom ?? ""],
      ["time_to", timeTo ?? ""],
    ].filter(([, v]) => v !== undefined && v !== "");

    const urlWithQsp = getUrlWithQsp(url, options);

    try {
      const filesResult = await fetchUrl(urlWithQsp);

      if (filesResult[branch]) {
        setFilesDiff(filesResult[branch]);
      }
    } catch (err) {
      setError(true);
    }

    setIsLoading(false);
  }, [branchname, branchOnly, timeFrom, timeTo, proposedChangesDetails?.source_branch?.value]);

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch: fetchFiles }));

  const setFilesInState = useCallback(async () => {
    await fetchFiles();
  }, []);

  useEffect(() => {
    setFilesInState();
  }, []);

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the files diff." />;
  }

  if (!Object.values(filesDiff).length) {
    return <NoDataFound message="No files diff for this branch." />;
  }

  return (
    <div className="text-sm">
      {Object.values(filesDiff).map((diff, index) => (
        <FileRepoDiff key={index} diff={diff} />
      ))}
    </div>
  );
});
