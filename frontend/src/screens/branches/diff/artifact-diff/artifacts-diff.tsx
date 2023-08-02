import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import "react-diff-view/style/index.css";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import { ALERT_TYPES, Alert } from "../../../../components/alert";
import { CONFIG } from "../../../../config/config";
import { PROPOSED_CHANGES_ARTIFACT_THREAD } from "../../../../config/constants";
import { QSP } from "../../../../config/qsp";
import { getProposedChangesArtifactsThreads } from "../../../../graphql/queries/proposed-changes/getProposedChangesArtifactsThreads";
import useQuery from "../../../../hooks/useQuery";
import { schemaState } from "../../../../state/atoms/schema.atom";
import { fetchUrl } from "../../../../utils/fetch";
import ErrorScreen from "../../../error-screen/error-screen";
import LoadingScreen from "../../../loading-screen/loading-screen";
import NoDataFound from "../../../no-data-found/no-data-found";
import { ArtifactRepoDiff } from "./artifact-repo-diff";

export type tArtifactsDiff = {
  proposedChangesDetails?: any;
};

export const ArtifactsDiff = (props: tArtifactsDiff) => {
  const { proposedChangesDetails } = props;

  const [artifactsDiff, setArtifactsDiff] = useState({});
  const { branchname, proposedchange } = useParams();
  const [schemaList] = useAtom(schemaState);
  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const [timeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);
  const [isLoading, setIsLoading] = useState(false);

  const schemaData = schemaList.filter((s) => s.name === PROPOSED_CHANGES_ARTIFACT_THREAD)[0];

  const queryString =
    schemaData && proposedchange
      ? getProposedChangesArtifactsThreads({
          id: proposedchange,
          kind: schemaData.kind,
          attributes: schemaData.attributes,
        })
      : "";

  const query = queryString
    ? gql`
        ${queryString}
      `
    : "";

  const { loading, error } = queryString
    ? useQuery(query, {
        skip: !schemaData && !proposedchange,
      })
    : { loading: false, error: null };

  const fetchFiles = useCallback(async () => {
    const branch = branchname || proposedChangesDetails?.source_branch?.value;

    if (!branch) return;

    setIsLoading(true);

    const url = CONFIG.ARTIFACTS_DIFF_URL(branch);

    const options: string[][] = [
      ["branch", branch ?? ""],
      ["branch_only", branchOnly ?? ""],
      ["time_from", timeFrom ?? ""],
      ["time_to", timeTo ?? ""],
    ].filter(([, v]) => v !== undefined && v !== "");

    const qsp = new URLSearchParams(options);

    const urlWithQsp = `${url}${options.length ? `&${qsp.toString()}` : ""}`;

    try {
      const filesResult = await fetchUrl(urlWithQsp);

      setArtifactsDiff(filesResult);
    } catch (err) {
      console.error("err: ", err);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading artifactsDiff diff" />);
    }

    setIsLoading(false);
  }, [branchname, branchOnly, timeFrom, timeTo, proposedChangesDetails?.source_branch?.value]);

  const setFilesInState = useCallback(async () => {
    await fetchFiles();
  }, []);

  useEffect(() => {
    setFilesInState();
  }, []);

  if (loading || isLoading) {
    return <LoadingScreen />;
  }

  if (error) {
    console.log("error: ", error);
    return <ErrorScreen />;
  }

  if (!Object.values(artifactsDiff).length) {
    return <NoDataFound />;
  }

  // const result = data ? data[schemaData?.kind]?.edges[0]?.node : {};

  return (
    <div className="text-sm">
      {Object.values(artifactsDiff).map((diff, index) => (
        <ArtifactRepoDiff key={index} diff={diff} />
      ))}
    </div>
  );
};
