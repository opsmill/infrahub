import { gql, useQuery } from "@apollo/client";
import { useAtom } from "jotai";
import { use } from "react";
import { useParams } from "react-router";

import {
  PROPOSED_CHANGES_OBJECT_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "@/shared/config/constants";

import { getThreadLabel } from "@/entities/diff/ui/diff-utils";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useDeleteObjectMutation } from "@/entities/nodes/object/ui/queries/delete-object.mutation";
import { getProposedChangesObjectThreadComments } from "@/entities/proposed-changes/api/getProposedChangesObjectThreadComments";
import { AddComment } from "@/entities/proposed-changes/ui/conversations/add-comment";
import { Thread } from "@/entities/proposed-changes/ui/conversations/thread";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { DiffContext } from ".";

type tDiffComments = {
  path: string;
  refetch?: Function;
};

export const DiffComments = (props: tDiffComments) => {
  const { path, refetch: parentRefetch } = props;

  const { proposedChangeId } = useParams();
  const [schemaList] = useAtom(nodeSchemasAtom);
  const { refetch: contextRefetch, node, currentBranch } = use(DiffContext);
  const createObject = useCreateObjectMutation();
  const deleteObject = useDeleteObjectMutation();

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT_THREAD_OBJECT);

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
    if (!comment) {
      return;
    }

    const label = getThreadLabel(node, currentBranch, path);

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
      resolved: {
        value: false,
      },
    };

    await createObject.mutateAsync(
      {
        objectKind: PROPOSED_CHANGES_OBJECT_THREAD_OBJECT,
        data: newThread,
      },
      {
        onSuccess: async (newThread) => {
          const threadId = newThread.id;

          const newComment = {
            text: {
              value: comment,
            },
            thread: {
              id: threadId,
            },
          };

          await createObject.mutateAsync(
            {
              objectKind: PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
              data: newComment,
            },
            {
              onSuccess: async () => {
                handleRefetch();
              },
              onError: async (error) => {
                if (threadId) {
                  await deleteObject.mutateAsync({
                    objectKind: PROPOSED_CHANGES_OBJECT_THREAD_OBJECT,
                    objectId: threadId,
                  });
                }

                console.error("An error occurred while creating the comment: ", error);
              },
            }
          );
        },
      }
    );
  };

  const thread = data ? data[PROPOSED_CHANGES_OBJECT_THREAD_OBJECT]?.edges[0]?.node : {};

  if (loading || error) {
    return null;
  }

  return (
    <div className="flex-1 overflow-auto p-4">
      {thread?.id && <Thread thread={thread} refetch={handleRefetch} />}

      {!thread?.id && <AddComment onSubmit={handleSubmit} />}
    </div>
  );
};
