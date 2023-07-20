import { gql, useReactiveVar } from "@apollo/client";
import { formatISO } from "date-fns";
import { useAtom } from "jotai";
import { useContext, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { AddComment } from "../../components/conversations/add-comment";
import { Comment } from "../../components/conversations/comment";
import { Thread, sortByDate } from "../../components/conversations/thread";
import {
  PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
  PROPOSED_CHANGES_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "../../config/constants";
import { AuthContext } from "../../decorators/withAuth";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { createObject } from "../../graphql/mutations/objects/createObject";
import { deleteObject } from "../../graphql/mutations/objects/deleteObject";
import { getProposedChangesConversations } from "../../graphql/queries/proposed-changes/getProposedChangesConversations";
import { branchVar } from "../../graphql/variables/branchVar";
import { dateVar } from "../../graphql/variables/dateVar";
import useQuery from "../../hooks/useQuery";
import { schemaState } from "../../state/atoms/schema.atom";
import { stringifyWithoutQuotes } from "../../utils/string";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";

export const Conversations = () => {
  const { proposedchange } = useParams();

  const [schemaList] = useAtom(schemaState);
  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);
  const [isLoading, setIsLoading] = useState(false);
  const auth = useContext(AuthContext);

  const schemaData = schemaList.filter((s) => s.name === PROPOSED_CHANGES_OBJECT)[0];

  const queryString = schemaData
    ? getProposedChangesConversations({
        id: proposedchange,
        kind: schemaData.kind,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data, refetch } = useQuery(query, { skip: !schemaData });

  if (!schemaData || loading) {
    return <LoadingScreen />;
  }

  if (error) {
    return <ErrorScreen />;
  }

  const result = data ? data[schemaData?.kind]?.edges[0]?.node : {};
  const threads = result?.threads?.edges?.map((edge: any) => edge.node);
  const comments = result?.comments?.edges?.map((edge: any) => edge.node);
  const list = sortByDate([...threads, ...comments]);

  const handleSubmit = async (data: any, event: any) => {
    let threadId;

    try {
      event.target.reset();

      if (!data || !auth?.data?.sub) {
        return;
      }

      const newDate = formatISO(new Date());

      const newThread = {
        change: {
          id: proposedchange,
        },
        created_at: {
          value: newDate,
        },
        resolved: {
          value: false,
        },
      };

      const threadMutationString = createObject({
        kind: PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
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

      threadId = result?.data[`${PROPOSED_CHANGES_CHANGE_THREAD_OBJECT}Create`]?.object?.id;

      const newComment = {
        text: {
          value: data.comment,
        },
        created_by: {
          id: auth?.data?.sub,
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
          name: PROPOSED_CHANGES_CHANGE_THREAD_OBJECT,
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

  return (
    <div className="max-w-2xl mx-auto pt-4">
      <div>
        {list.map((item: any, index: number) => {
          if (item.__typename === "CoreChangeThread") {
            return <Thread key={index} thread={item} refetch={refetch} />;
          }

          return <Comment key={index} comment={item} />;
        })}
      </div>

      <div>
        <AddComment
          onSubmit={handleSubmit}
          isLoading={isLoading}
          disabled={!auth?.permissions?.write}
        />
      </div>
    </div>
  );
};
