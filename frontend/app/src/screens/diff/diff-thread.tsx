import { SidePanelTitle } from "@/components/display/sidepanel-title";
import SlideOver from "@/components/display/slide-over";
import { Tooltip } from "@/components/ui/tooltip";
import { PROPOSED_CHANGES_OBJECT_THREAD_OBJECT } from "@/config/constants";
import { getProposedChangesObjectThreads } from "@/graphql/queries/proposed-changes/getProposedChangesObjectThreads";
import { useAuth } from "@/hooks/useAuth";
import useQuery from "@/hooks/useQuery";
import { schemaState } from "@/state/atoms/schema.atom";
import { getThreadLabel, getThreadTitle } from "@/utils/diff";
import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { useContext, useState } from "react";
import { useParams } from "react-router-dom";
import { DiffContext } from "./data-diff";
import { DataDiffComments } from "./diff-comments";
import { Icon } from "@iconify-icon/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/buttons/button-primitive";

type tDataDiffThread = {
  path: string;
};

export const DataDiffThread = (props: tDataDiffThread) => {
  const { path } = props;

  const { proposedchange } = useParams();
  const [schemaList] = useAtom(schemaState);
  const auth = useAuth();
  const { node, currentBranch } = useContext(DiffContext);
  const [showThread, setShowThread] = useState(false);

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT_THREAD_OBJECT);

  const queryString = schemaData
    ? getProposedChangesObjectThreads({
        id: proposedchange,
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

  const thread = data ? data[PROPOSED_CHANGES_OBJECT_THREAD_OBJECT]?.edges[0]?.node : {};

  if (loading || error) {
    return null;
  }

  const title = (
    <SidePanelTitle title="Conversation" hideBranch>
      {getThreadTitle(thread, getThreadLabel(node, currentBranch, path))}
    </SidePanelTitle>
  );

  return (
    <div className="ml-2">
      <div className="flex items-center cursor-pointer ">
        {thread?.comments?.count && (
          <Badge variant={"dark-gray"} className="rounded-full mr-2">
            <Icon icon="mdi:chat-outline" className="mr-1" />
            {thread?.comments?.count}
          </Badge>
        )}
        <div className="hidden group-hover:block">
          <Tooltip enabled content={"Add comment"}>
            <Button
              disabled={!auth?.permissions?.write}
              onClick={() => {
                setShowThread(true);
              }}
              className="p-0 h-6"
              variant={"outline"}
              size={"icon"}
              data-cy="data-diff-add-reply">
              <Icon icon={"mdi:plus"} />
            </Button>
          </Tooltip>
        </div>
      </div>

      <SlideOver title={title} open={showThread} setOpen={setShowThread}>
        <DataDiffComments path={path} refetch={refetch} />

        <div className="flex items-center justify-end gap-x-6 py-3 pr-3 border-t">
          <Button onClick={() => setShowThread(false)}>Close</Button>
        </div>
      </SlideOver>
    </div>
  );
};
