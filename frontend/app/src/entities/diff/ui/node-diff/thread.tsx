import { Icon } from "@iconify-icon/react";
import { Button, Tooltip } from "@infrahub/ui";
import { useState } from "react";
import { useParams } from "react-router";

import { SidePanelTitle } from "@/shared/components/display/sidepanel-title";
import SlideOver from "@/shared/components/display/slide-over";

import { getThreadLabel, getThreadTitle } from "@/entities/diff/ui/diff-utils";
import { useGetDiffThread } from "@/entities/diff/ui/queries/get-diff-thread.query";
import { getPermission } from "@/entities/permission/utils";

import { DiffComments } from "./comments";

type tDiffThread = {
  path: string;
};

export const DiffThread = ({ path }: tDiffThread) => {
  const { proposedChangeId } = useParams();
  const [showThread, setShowThread] = useState(false);

  const { isLoading, error, data, refetch } = useGetDiffThread(
    { proposedChangeId: proposedChangeId ?? "", objectPath: path },
    { enabled: !!proposedChangeId }
  );

  const thread = data?.thread;

  const permission = data && getPermission(data?.permissions?.edges);

  if (!proposedChangeId || isLoading || error) {
    return null;
  }

  const title = (
    <SidePanelTitle title="Conversation" hideBranch>
      {getThreadTitle(thread, getThreadLabel(path))}
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
                size={"xs"}
                shape={"circle"}
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
