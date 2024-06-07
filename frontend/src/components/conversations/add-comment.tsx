import { ReactElement } from "react";
import DynamicForm from "../form/dynamic-form";
import { DynamicFieldProps } from "../form/fields/common";
import { SCHEMA_ATTRIBUTE_KIND } from "../../config/constants";
import { useAuth } from "../../hooks/useAuth";
import { LinkButton } from "../buttons/button-primitive";
import { constructPath } from "../../utils/fetch";
import { useLocation } from "react-router-dom";

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

export const AddComment = ({ onSubmit, onCancel }: tAddComment) => {
  const location = useLocation();
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return (
      <DynamicForm
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
};
