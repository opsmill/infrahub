import { Button, Sheet, Tooltip } from "@infrahub/ui";
import { useState } from "react";
import { useParams } from "react-router";

import { Icon } from "@/shared/components/display/icon";

import { getThreadLabel, getThreadTitle } from "@/entities/diff/ui/diff-utils";
import { useGetDiffThread } from "@/entities/diff/ui/queries/get-diff-thread.query";
import { getPermission } from "@/entities/permission/domain/rules/get-permission";

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

  return (
    <>
      <div className="flex cursor-pointer items-center">
        {thread?.comments?.count ? (
          <Tooltip message={"Add comment"}>
            <Button
              isDisabled={!permission?.create?.isAllowed}
              onPress={() => setShowThread(true)}
              className="h-6 rounded-full"
              size="xs"
              variant="outline"
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

      <Sheet isOpen={showThread} onOpenChange={setShowThread}>
        <div className="mb-2 font-semibold text-lg">Conversation</div>
        {getThreadTitle(thread, getThreadLabel(path))}
        <DiffComments path={path} refetch={refetch} />
      </Sheet>
    </>
  );
};
