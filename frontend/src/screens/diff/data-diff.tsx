import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { createContext, useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { CONFIG } from "../../config/config";
import {
  PROPOSED_CHANGES_OBJECT_THREAD,
  PROPOSED_CHANGES_OBJECT_THREAD_OBJECT,
} from "../../config/constants";
import { QSP } from "../../config/qsp";
import { getProposedChangesObjectGlobalThreads } from "../../graphql/queries/proposed-changes/getProposedChangesObjectGlobalThreads";
import useQuery from "../../hooks/useQuery";
import { proposedChangedState } from "../../state/atoms/proposedChanges.atom";
import { schemaState } from "../../state/atoms/schema.atom";
import { fetchUrl } from "../../utils/fetch";
import LoadingScreen from "../loading-screen/loading-screen";
import { DataDiffNode, tDataDiffNode } from "./data-diff-node";

type tDiffContext = {
  refetch?: Function;
  node?: tDataDiffNode;
  currentBranch?: string;
};

export const DiffContext = createContext<tDiffContext>({});

export const DataDiff = () => {
  const { branchname, proposedchange } = useParams();

  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
  const [timeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
  const [timeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);
  const [proposedChangesDetails] = useAtom(proposedChangedState);
  const [schemaList] = useAtom(schemaState);
  const [diff, setDiff] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const branch = branchname || proposedChangesDetails?.source_branch?.value;

  const schemaData = schemaList.filter((s) => s.name === PROPOSED_CHANGES_OBJECT_THREAD)[0];

  const queryString = schemaData
    ? getProposedChangesObjectGlobalThreads({
        id: proposedchange,
        kind: schemaData.kind,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { data, refetch } = useQuery(query, { skip: !schemaData });

  // Get the comments count per object path like { [path]: [count] }, and include all sub path for each object
  const objectComments =
    data &&
    data[PROPOSED_CHANGES_OBJECT_THREAD_OBJECT]?.edges
      .map((edge: any) => edge.node)
      .reduce((acc: any, node: any) => {
        const objectPathResult = node?.object_path?.value?.match(/^\w+\/(\w|-)+/g);

        const objectPath = objectPathResult && objectPathResult[0];

        if (!objectPath) {
          return;
        }

        return {
          ...acc,
          // Count all comments for this object (will include comments on sub nodes)
          [objectPath]: (acc[objectPath] ?? 0) + (node?.comments?.count ?? 0),
        };
      }, {});

  const fetchDiffDetails = useCallback(async () => {
    if (!branch) return;

    setIsLoading(true);

    const url = CONFIG.DATA_DIFF_URL(branch);

    const options: string[][] = [
      ["branch_only", branchOnly ?? "false"],
      ["time_from", timeFrom ?? ""],
      ["time_to", timeTo ?? ""],
    ].filter(([, v]) => v !== undefined && v !== "");

    const qsp = new URLSearchParams(options);

    const urlWithQsp = `${url}${options.length ? `&${qsp.toString()}` : ""}`;

    try {
      const diffDetails = await fetchUrl(urlWithQsp);

      setDiff(diffDetails.diffs ?? []);
    } catch (err) {
      console.error("err: ", err);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading branch diff" />);
    }

    setIsLoading(false);
  }, [branchname, branchOnly, timeFrom, timeTo]);

  useEffect(() => {
    fetchDiffDetails();
  }, [fetchDiffDetails]);

  const renderNode = (node: any, index: number) => {
    // Provide threads and comments counts to display in the top level node
    const commentsCount = objectComments && objectComments[node?.path];

    const currentBranch =
      branch ?? branchname ?? proposedChangesDetails?.source_branch?.value ?? "main";

    const context = {
      // Provide refetch function to update count on comment
      refetch,
      node,
      currentBranch,
    };

    return (
      <DiffContext.Provider key={index} value={context}>
        <DataDiffNode node={node} commentsCount={commentsCount} />
      </DiffContext.Provider>
    );
  };

  return (
    <>
      {(!branchOnly || branchOnly === "false") && (
        <div className="flex items-center m-4">
          <span className="mr-2">Branches colours:</span>
          <div className={"rounded-lg shadow p-2 mr-2 bg-custom-blue-10"}>main</div>
          <div className={"rounded-lg shadow p-2 bg-green-200"}>{branch}</div>
        </div>
      )}

      {isLoading && <LoadingScreen />}

      {!isLoading && <div className="text-xs">{diff?.map(renderNode)}</div>}
    </>
  );
};
