import { gql, useQuery } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { use, useState } from "react";
import { useParams } from "react-router";

import { SidePanelTitle } from "@/shared/components/display/sidepanel-title";
import SlideOver from "@/shared/components/display/slide-over";
import { Button } from "@/shared/components/ui/button";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { PROPOSED_CHANGES_OBJECT_THREAD_OBJECT } from "@/shared/config/constants";

import { getThreadLabel, getThreadTitle } from "@/entities/diff/utils";
import { getPermission } from "@/entities/permission/utils";
import { getProposedChangesObjectThreads } from "@/entities/proposed-changes/api/getProposedChangesObjectThreads";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { DiffContext } from ".";
import { DiffComments } from "./comments";

type tDiffThread = {
  path: string;
};

export const DiffThread = ({ path }: tDiffThread) => {
  const { proposedChangeId } = useParams();
  const [schemaList] = useAtom(nodeSchemasAtom);
  const { node, currentBranch } = use(DiffContext);
  const [showThread, setShowThread] = useState(false);

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT_THREAD_OBJECT);

  const queryString = schemaData
    ? getProposedChangesObjectThreads({
        id: proposedChangeId,
        path,
        kind: schemaData.kind,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data, refetch } = useQuery(query, { skip: !schemaData });

  const thread = data ? data[schemaData.kind]?.edges[0]?.node : {};

  const permission = data && getPermission(data?.[schemaData.kind]?.permissions?.edges);

  if (loading || error) {
    return null;
  }

  const title = (
    <SidePanelTitle title="Conversation" hideBranch>
      {getThreadTitle(thread, getThreadLabel(node, currentBranch, path))}
    </SidePanelTitle>
  );

  return (
    <>
      <div className="flex cursor-pointer items-center">
        {thread?.comments?.count ? (
          <Tooltip enabled content={"Add comment"}>
            <Button
              disabled={!permission?.create?.isAllowed}
              onClick={(event) => {
                event.stopPropagation();
                setShowThread(true);
              }}
              className="h-6 rounded-full px-2"
              variant={"dark"}
              data-testid="data-diff-add-comment"
            >
              <Icon icon="mdi:chat-outline" className="mr-1" />
              {thread?.comments?.count}
            </Button>
          </Tooltip>
        ) : (
          <div className="hidden group-hover:block">
            <Tooltip enabled content={"Add comment"}>
              <Button
                disabled={!permission?.create?.isAllowed}
                onClick={(event) => {
                  event.stopPropagation();
                  setShowThread(true);
                }}
                className="h-6 rounded-full p-0"
                variant={"outline"}
                size={"icon"}
                data-testid="data-diff-add-comment"
              >
                <Icon icon={"mdi:plus"} />
              </Button>
            </Tooltip>
          </div>
        )}
      </div>

      <SlideOver title={title} open={showThread} setOpen={setShowThread}>
        <DiffComments path={path} refetch={refetch} />

        <div className="flex items-center justify-end gap-x-6 border-gray-200 border-t py-3 pr-3">
          <Button onClick={() => setShowThread(false)}>Close</Button>
        </div>
      </SlideOver>
    </>
  );
};
