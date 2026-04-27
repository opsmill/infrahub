import { useQuery } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { use, useState } from "react";
import { useParams } from "react-router";

import { Button } from "@/shared/components/aria/button";
import { Tooltip } from "@/shared/components/aria/tooltip";
import { SidePanelTitle } from "@/shared/components/display/sidepanel-title";
import SlideOver from "@/shared/components/display/slide-over";

import { getThreadLabel, getThreadTitle } from "@/entities/diff/ui/diff-utils";
import { getPermission } from "@/entities/permission/utils";
import { GET_OBJECT_THREADS } from "@/entities/proposed-changes/api/getProposedChangesObjectThreads";

import { DiffContext } from ".";
import { DiffComments } from "./comments";

type tDiffThread = {
  path: string;
};

export const DiffThread = ({ path }: tDiffThread) => {
  const { proposedChangeId } = useParams();
  const { node, currentBranch } = use(DiffContext);
  const [showThread, setShowThread] = useState(false);

  const { loading, error, data, refetch } = useQuery(GET_OBJECT_THREADS, {
    variables: { changeIds: [proposedChangeId!], objectPath: path },
    skip: !proposedChangeId,
  });

  const thread = data?.CoreObjectThread?.edges?.[0]?.node;

  const permission = data && getPermission(data?.CoreObjectThread?.permissions?.edges);

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
          <Tooltip message={"Add comment"}>
            <Button
              isDisabled={!permission?.create?.isAllowed}
              onPress={() => setShowThread(true)}
              className="h-6 rounded-full bg-gray-200 px-2 shadow-xs data-hovered:bg-gray-300"
              variant={"ghost"}
              data-testid="data-diff-add-comment"
            >
              <Icon icon="mdi:chat-outline" />
              {thread?.comments?.count}
            </Button>
          </Tooltip>
        ) : (
          <div className="hidden group-hover:block">
            <Tooltip message={"Add comment"}>
              <Button
                isDisabled={!permission?.create?.isAllowed}
                onPress={() => setShowThread(true)}
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
          <Button onPress={() => setShowThread(false)}>Close</Button>
        </div>
      </SlideOver>
    </>
  );
};
