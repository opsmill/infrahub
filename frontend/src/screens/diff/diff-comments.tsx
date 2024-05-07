import { gql } from "@apollo/client";
import { formatISO } from "date-fns";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useContext, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { AddComment } from "../../components/conversations/add-comment";
import { Thread } from "../../components/conversations/thread";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import {
  PROPOSED_CHANGES_OBJECT_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "../../config/constants";
import { useAuth } from "../../hooks/useAuth";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { createObject } from "../../graphql/mutations/objects/createObject";
import { deleteObject } from "../../graphql/mutations/objects/deleteObject";
import { getProposedChangesObjectThreadComments } from "../../graphql/queries/proposed-changes/getProposedChangesObjectThreadComments";
import useQuery from "../../hooks/useQuery";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { schemaState } from "../../state/atoms/schema.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { getThreadLabel } from "../../utils/diff";
import { stringifyWithoutQuotes } from "../../utils/string";
import { DiffContext } from "./data-diff";

type tDataDiffComments = {
  path: string;
  refetch?: Function;
};

export const DataDiffComments = (props: tDataDiffComments) => {
  const { path, refetch: parentRefetch } = props;

  const { proposedchange } = useParams();
  const [schemaList] = useAtom(schemaState);
  const auth = useAuth();
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [isLoading, setIsLoading] = useState(false);
  const { refetch: contextRefetch, node, currentBranch } = useContext(DiffContext);

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT_THREAD_OBJECT);

  const approverId = auth?.data?.sub;

  const queryString = schemaData
    ? getProposedChangesObjectThreadComments({
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

  const handleRefetch = () => {
    refetch();

    if (parentRefetch) {
      parentRefetch();
    }

    if (contextRefetch) {
      contextRefetch();
    }
  };

  const handleSubmit = async ({ comment }: { comment: string }) => {
    let threadId;

    try {
      if (!comment || !approverId) {
        return;
      }

      const label = getThreadLabel(node, currentBranch, path);

      const newDate = formatISO(new Date());

      const newThread = {
        change: {
          id: proposedchange,
        },
        label: {
          value: label,
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

      const threadMutationString = createObject({
        kind: PROPOSED_CHANGES_OBJECT_THREAD_OBJECT,
        data: stringifyWithoutQuotes(newThread),
      });

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

      threadId = result?.data[`${PROPOSED_CHANGES_OBJECT_THREAD_OBJECT}Create`]?.object?.id;

      const newComment = {
        text: {
          value: comment,
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

      handleRefetch();

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

      console.error("An error occurred while creating the comment: ", error);

      setIsLoading(false);
    }
  };

  const thread = data ? data[PROPOSED_CHANGES_OBJECT_THREAD_OBJECT]?.edges[0]?.node : {};

  if (loading || error) {
    return null;
  }

  return (
    <div className="flex-1 p-4 overflow-auto">
      {thread?.id && <Thread thread={thread} refetch={handleRefetch} />}

      {!thread?.id && (
        <AddComment
          onSubmit={handleSubmit}
          isLoading={isLoading}
          disabled={!auth?.permissions?.write}
        />
      )}
    </div>
  );
};
