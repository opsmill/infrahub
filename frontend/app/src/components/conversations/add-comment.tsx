import { Button, LinkButton } from "@/components/buttons/button-primitive";
import { useAuth } from "@/hooks/useAuth";
import { constructPath } from "@/utils/fetch";
import React, { forwardRef, ReactElement } from "react";
import { useLocation } from "react-router-dom";
import { Form, FormRef, FormSubmit } from "@/components/ui/form";
import TextareaField from "@/components/form/fields/textarea.field";
import { isRequired } from "@/components/form/utils/validation";

type CommentFormData = {
  comment: string;
};

type tAddComment = {
  onSubmit: ({ comment }: CommentFormData) => Promise<void>;
  onCancel?: () => void;
  additionalButtons?: ReactElement;
};

export const AddComment = forwardRef<FormRef, tAddComment>(({ onSubmit, onCancel }, ref) => {
  const location = useLocation();
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
        }}>
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
            <Button variant="outline" className="mr-2" onClick={onCancel}>
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
      <LinkButton
        size="sm"
        variant="primary"
        to={constructPath("/signin")}
        state={{ from: location }}>
        Sign in
      </LinkButton>{" "}
      to be able to add a comment.
    </div>
  );
});
