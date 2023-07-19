import { gql, useReactiveVar } from "@apollo/client";
import { useState } from "react";
import { toast } from "react-toastify";
import { PROPOSED_CHANGES_THREAD_COMMENT_OBJECT } from "../../config/constants";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { createObject } from "../../graphql/mutations/objects/createObject";
import { branchVar } from "../../graphql/variables/branchVar";
import { dateVar } from "../../graphql/variables/dateVar";
import { stringifyWithoutQuotes } from "../../utils/string";
import { ALERT_TYPES, Alert } from "../alert";
import { AddComment } from "./add-comment";
import { Comment } from "./comment";

type tThread = {
  thread: any;
  refetch: Function;
};

export const Thread = (props: tThread) => {
  const { thread, refetch } = props;

  const { comments } = thread;

  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (data?: any) => {
    try {
      if (!data) {
        return;
      }

      const newObject = {
        text: {
          value: data.comment,
        },
        thread: {
          id: thread.id,
        },
      };

      const mutationString = createObject({
        kind: PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
        data: stringifyWithoutQuotes(newObject),
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
    <section className="bg-custom-white p-4 mb-4 rounded-lg">
      <div className="">
        {comments.edges.map((comment: any, index: number) => (
          <Comment key={index} comment={comment.node} className={"border border-gray-200"} />
        ))}
      </div>

      <AddComment onSubmit={handleSubmit} isLoading={isLoading} />
    </section>
  );
};
