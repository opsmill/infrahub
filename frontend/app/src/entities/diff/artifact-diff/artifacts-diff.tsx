import { useAtom } from "jotai";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from "react";

import { fetchUrl, getUrlWithQsp } from "@/shared/api/rest/fetch";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { CONFIG } from "@/shared/config/config";
import { QSP } from "@/shared/config/qsp";

import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import "react-diff-view/style/index.css";

import { useQueryState } from "nuqs";
import { useParams } from "react-router";
import { toast } from "react-toastify";

import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { ArtifactRepoDiff } from "./artifact-repo-diff";

export const ArtifactsDiff = forwardRef((_, ref) => {
  const [artifactsDiff, setArtifactsDiff] = useState({});
  const { "*": branchName } = useParams();
  const [branchOnly] = useQueryState(QSP.BRANCH_FILTER_BRANCH_ONLY);
  const [timeFrom] = useQueryState(QSP.BRANCH_FILTER_TIME_FROM);
  const [timeTo] = useQueryState(QSP.BRANCH_FILTER_TIME_TO);
  const [proposedChangesDetails] = useAtom(proposedChangedState);
  const [isLoading, setIsLoading] = useState(false);

  const fetchFiles = useCallback(async () => {
    const branch = branchName || proposedChangesDetails?.source_branch?.value;

    if (!branch) return;

    setIsLoading(true);

    const url = CONFIG.ARTIFACTS_DIFF_URL(branch);

    const options: string[][] = [
      ["branch_only", branchOnly ?? ""],
      ["time_from", timeFrom ?? ""],
      ["time_to", timeTo ?? ""],
    ].filter(([, v]) => v !== undefined && v !== "");

    const urlWithQsp = getUrlWithQsp(url, options);

    try {
      const filesResult = await fetchUrl(urlWithQsp);

      setArtifactsDiff(filesResult);
    } catch (err) {
      console.error("Error while loading artifacts diff: ", err);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading artifacts diff" />);
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

  if (!Object.values(artifactsDiff).length) {
    return <NoDataFound message="No artifact found." />;
  }

  return (
    <div className="text-sm">
      {Object.values(artifactsDiff).map((diff, index) => (
        <ArtifactRepoDiff key={index} diff={diff} />
      ))}
    </div>
  );
});
