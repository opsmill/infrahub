import { CONFIG } from "@/config/config";
import { QSP } from "@/config/qsp";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { fetchUrl, getUrlWithQsp } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { useAtom } from "jotai";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from "react";
import "react-diff-view/style/index.css";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { useParams } from "react-router";
import { StringParam, useQueryParam } from "use-query-params";
import { FileRepoDiff } from "./file-repo-diff";

export const FilesDiff = forwardRef((_, ref) => {
  const [filesDiff, setFilesDiff] = useState({});
  const { "*": branchName } = useParams();
  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const [timeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(false);
  const [proposedChangesDetails] = useAtom(proposedChangedState);

  const fetchFiles = useCallback(async () => {
    const branch = branchName || proposedChangesDetails?.source_branch?.value;

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
    } catch (error) {
      console.error(error);
      setError(true);
    }

    setIsLoading(false);
  }, [branchName, branchOnly, timeFrom, timeTo, proposedChangesDetails?.source_branch?.value]);

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch: fetchFiles }));

  const setFilesInState = useCallback(async () => {
    await fetchFiles();
  }, []);

  useEffect(() => {
    setFilesInState();
  }, []);

  if (isLoading) {
    return <LoadingIndicator className="p-4" />;
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
