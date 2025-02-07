import {
  PROPOSED_CHANGES_OBJECT_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "@/config/constants";
import { useAuth } from "@/entities/authentication/ui/useAuth";
import { currentBranchAtom } from "@/entities/branches/stores";
import { getThreadLabel } from "@/entities/diff/utils";
import { createObject } from "@/entities/nodes/api/createObject";
import { deleteObject } from "@/entities/nodes/api/deleteObject";
import { getProposedChangesObjectThreadComments } from "@/entities/proposed-changes/api/getProposedChangesObjectThreadComments";
import { schemaState } from "@/entities/schema/stores/schema.atom";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import useQuery from "@/shared/api/graphql/useQuery";
import { AddComment } from "@/shared/components/conversations/add-comment";
import { Thread } from "@/shared/components/conversations/thread";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { formatISO } from "date-fns";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useContext } from "react";
import { useParams } from "react-router";
import { DiffContext } from ".";

type tDiffComments = {
  path: string;
  refetch?: Function;
};

export const DiffComments = (props: tDiffComments) => {
  const { path, refetch: parentRefetch } = props;

  const { proposedChangeId } = useParams();
  const [schemaList] = useAtom(schemaState);
  const auth = useAuth();
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const { refetch: contextRefetch, node, currentBranch } = useContext(DiffContext);

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT_THREAD_OBJECT);

  const approverId = auth?.data?.sub;

  const queryString = schemaData
    ? getProposedChangesObjectThreadComments({
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
          id: proposedChangeId,
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

      handleRefetch();
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
    }
  };

  const thread = data ? data[PROPOSED_CHANGES_OBJECT_THREAD_OBJECT]?.edges[0]?.node : {};

  if (loading || error) {
    return null;
  }

  return (
    <div className="flex-1 p-4 overflow-auto">
      {thread?.id && <Thread thread={thread} refetch={handleRefetch} />}

      {!thread?.id && <AddComment onSubmit={handleSubmit} />}
    </div>
  );
};
