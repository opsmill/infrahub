import type React from "react";

import { constructPath } from "@/shared/api/rest/fetch";
import { Button, LinkButton } from "@/shared/components/aria/button";
import TextareaField from "@/shared/components/form/fields/textarea.field";
import { isRequired } from "@/shared/components/form/utils/validation";
import { Form, type FormRef, FormSubmit } from "@/shared/components/ui/form";

import { useAuth } from "@/entities/authentication/ui/useAuth";

interface CommentFormData {
  comment: string;
}

interface AddCommentProps {
  ref?: React.Ref<FormRef>;
  onSubmit: ({ comment }: CommentFormData) => Promise<void>;
  onCancel?: () => void;
  additionalButtons?: React.ReactElement;
}

export const AddComment = ({ ref, onSubmit, onCancel }: AddCommentProps) => {
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return (
      <Form
        ref={ref}
        onSubmit={async ({ comment }) => {
          const commentFormData: CommentFormData = {
            comment: comment.value as string,
          };
          await onSubmit(commentFormData);
        }}
      >
        <TextareaField
          name="comment"
          label="Add a comment"
          placeholder="Add your comment here..."
          rules={{
            validate: {
              required: isRequired,
            },
          }}
        />

        <div className="text-right">
          {onCancel && (
            <Button variant="outline" className="mr-2" onPress={onCancel}>
              Cancel
            </Button>
          )}
          <FormSubmit>Comment</FormSubmit>
        </div>
      </Form>
    );
  }

  return (
    <div>
      <LinkButton size="sm" variant="primary" href={constructPath("/login")}>
        Login
      </LinkButton>{" "}
      to be able to add a comment.
    </div>
  );
};
