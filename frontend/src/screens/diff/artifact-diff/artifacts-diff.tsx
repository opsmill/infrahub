import { useAtom } from "jotai";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from "react";
import "react-diff-view/style/index.css";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import { ALERT_TYPES, Alert } from "../../../components/utils/alert";
import { CONFIG } from "../../../config/config";
import { QSP } from "../../../config/qsp";
import { proposedChangedState } from "../../../state/atoms/proposedChanges.atom";
import { fetchUrl, getUrlWithQsp } from "../../../utils/fetch";
import LoadingScreen from "../../loading-screen/loading-screen";
import NoDataFound from "../../no-data-found/no-data-found";
import { ArtifactRepoDiff } from "./artifact-repo-diff";

export const ArtifactsDiff = forwardRef((props, ref) => {
  const [artifactsDiff, setArtifactsDiff] = useState({});
  const { branchname } = useParams();
  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const [timeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);
  const [proposedChangesDetails] = useAtom(proposedChangedState);
  const [isLoading, setIsLoading] = useState(false);

  const fetchFiles = useCallback(async () => {
    const branch = branchname || proposedChangesDetails?.source_branch?.value;

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

  if (!Object.values(artifactsDiff).length) {
    return <NoDataFound message="No artifact found." />;
  }

  // const result = data ? data[schemaData?.kind]?.edges[0]?.node : {};

  return (
    <div className="text-sm">
      {Object.values(artifactsDiff).map((diff, index) => (
        <ArtifactRepoDiff key={index} diff={diff} />
      ))}
    </div>
  );
});
