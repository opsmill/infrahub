import { LinkButton } from "@/components/buttons/button-primitive";
import DynamicForm from "@/components/form/dynamic-form";
import { DynamicFieldProps } from "@/components/form/type";
import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import { useAuth } from "@/hooks/useAuth";
import { constructPath } from "@/utils/fetch";
import { forwardRef, ReactElement } from "react";
import { useLocation } from "react-router-dom";
import { FormRef } from "@/components/ui/form";

const fields: Array<DynamicFieldProps> = [
  {
    name: "comment",
    label: "Add a comment",
    placeholder: "Add your comment here...",
    type: SCHEMA_ATTRIBUTE_KIND.TEXTAREA,
    rules: {
      required: true,
    },
  },
];

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
      <DynamicForm
        ref={ref}
        fields={fields}
        onCancel={onCancel}
        onSubmit={async (data) => {
          await onSubmit(data as CommentFormData);
        }}
        submitLabel="Comment"
      />
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
