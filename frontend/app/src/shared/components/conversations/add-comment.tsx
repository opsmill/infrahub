import { forwardRef, type ReactElement } from "react";
import { useLocation } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Button, LinkButton } from "@/shared/components/buttons/button-primitive";
import TextareaField from "@/shared/components/form/fields/textarea.field";
import { isRequired } from "@/shared/components/form/utils/validation";
import { Form, type FormRef, FormSubmit } from "@/shared/components/ui/form";

import { useAuth } from "@/entities/authentication/ui/useAuth";

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
        to={constructPath("/login")}
        state={{ from: location }}
      >
        Login
      </LinkButton>{" "}
      to be able to add a comment.
    </div>
  );
});
