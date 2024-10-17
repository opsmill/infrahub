import { Button, LinkButton } from "@/components/buttons/button-primitive";
import TextareaField from "@/components/form/fields/textarea.field";
import { isRequired } from "@/components/form/utils/validation";
import { Form, FormRef, FormSubmit } from "@/components/ui/form";
import { useAuth } from "@/hooks/useAuth";
import { constructPath } from "@/utils/fetch";
import { ReactElement, forwardRef } from "react";
import { useLocation } from "react-router-dom";

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
