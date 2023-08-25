import { gql, useReactiveVar } from "@apollo/client";
import { PlusIcon } from "@heroicons/react/24/outline";
import { formatISO } from "date-fns";
import { useAtom } from "jotai";
import { useContext, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../../components/alert";
import { AddComment } from "../../../components/conversations/add-comment";
import { Thread } from "../../../components/conversations/thread";
import { BUTTON_TYPES, RoundedButton } from "../../../components/rounded-button";
import SlideOver from "../../../components/slide-over";
import { Tooltip } from "../../../components/tooltip";
import {
  PROPOSED_CHANGES_OBJECT_THREAD,
  PROPOSED_CHANGES_OBJECT_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "../../../config/constants";
import { AuthContext } from "../../../decorators/withAuth";
import graphqlClient from "../../../graphql/graphqlClientApollo";
import { createObject } from "../../../graphql/mutations/objects/createObject";
import { deleteObject } from "../../../graphql/mutations/objects/deleteObject";
import { getProposedChangesObjectThreads } from "../../../graphql/queries/proposed-changes/getProposedChangesObjectThreads";
import { branchVar } from "../../../graphql/variables/branchVar";
import { dateVar } from "../../../graphql/variables/dateVar";
import useQuery from "../../../hooks/useQuery";
import { schemaState } from "../../../state/atoms/schema.atom";
import { stringifyWithoutQuotes } from "../../../utils/string";

type tDataDiffComments = {
  path: string;
};

export const DataDiffComments = (props: tDataDiffComments) => {
  const { path } = props;

  const { proposedchange } = useParams();
  const [schemaList] = useAtom(schemaState);
  const auth = useContext(AuthContext);
  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);
  const [showThread, setShowThread] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const schemaData = schemaList.filter((s) => s.name === PROPOSED_CHANGES_OBJECT_THREAD)[0];

  const approverId = auth?.data?.sub;

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

  const handleSubmit = async (data: any, event: any) => {
    let threadId;

    try {
      event.target.reset();

      if (!data || !approverId) {
        return;
      }

      const newDate = formatISO(new Date());

      const newThread = {
        change: {
          id: proposedchange,
        },
        object_path: {
          value: path,
        },
        created_at: {
          value: newDate,
        },
        resolved: {
          value: false,
        },
      };

      console.log("newThread: ", newThread);

      const threadMutationString = createObject({
        kind: PROPOSED_CHANGES_OBJECT_THREAD_OBJECT,
        data: stringifyWithoutQuotes(newThread),
      });

      console.log("threadMutationString: ", threadMutationString);
      const threadMutation = gql`
        ${threadMutationString}
      `;

      const result = await graphqlClient.mutate({
        mutation: threadMutation,
        context: {
          branch: branch?.name,
          date,
        },
      });

      console.log("result: ", result);
      threadId = result?.data[`${PROPOSED_CHANGES_OBJECT_THREAD_OBJECT}Create`]?.object?.id;

      const newComment = {
        text: {
          value: data.comment,
        },
        created_by: {
          id: approverId,
        },
        created_at: {
          value: newDate,
        },
        thread: {
          id: threadId,
        },
      };

      const mutationString = createObject({
        kind: PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
        data: stringifyWithoutQuotes(newComment),
      });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: {
          branch: branch?.name,
          date,
        },
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Comment added"} />);

      refetch();

      setIsLoading(false);
    } catch (error: any) {
      if (threadId) {
        const mutationString = deleteObject({
          name: PROPOSED_CHANGES_OBJECT_THREAD_OBJECT,
          data: stringifyWithoutQuotes({
            id: threadId,
          }),
        });

        const mutation = gql`
          ${mutationString}
        `;

        await graphqlClient.mutate({
          mutation,
          context: { branch: branch?.name, date },
        });
        return;
      }

      console.error("An error occured while creating the comment: ", error);

      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={"An error occured while creating the comment"}
          details={error.message}
        />
      );

      setIsLoading(false);
    }
  };

  const thread = data ? data[PROPOSED_CHANGES_OBJECT_THREAD_OBJECT]?.edges[0]?.node : {};

  if (loading || error) {
    return null;
  }

  return (
    <div>
      <div className="hidden group-hover:block">
        <Tooltip message={"Add comment"}>
          <RoundedButton
            disabled={!auth?.permissions?.write}
            onClick={() => {
              console.log("CLICK");
              setShowThread(true);
            }}
            className="p-1"
            type={BUTTON_TYPES.DEFAULT}>
            {/* Display either a pill with the number of comments, or a plus icon to add a comment */}
            <PlusIcon className="h-4 w-4 " aria-hidden="true" />
          </RoundedButton>
        </Tooltip>
      </div>

      <SlideOver title={"Conversation"} open={showThread} setOpen={setShowThread}>
        <div className="flex-1 p-4 overflow-auto">
          {thread?.id && <Thread thread={thread} refetch={refetch} />}

          {!thread?.id && (
            <AddComment
              onSubmit={handleSubmit}
              isLoading={isLoading}
              disabled={!auth?.permissions?.write}
            />
          )}
        </div>
      </SlideOver>
    </div>
  );
};
