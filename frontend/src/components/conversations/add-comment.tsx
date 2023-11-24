import { ReactElement, useRef } from "react";
import { MarkdownEditor } from "../../screens/proposed-changes/MarkdownEditor";
import { Button, BUTTON_TYPES } from "../button";
import { MDXEditorMethods } from "@mdxeditor/editor";

type tAddComment = {
  onSubmit: (data: string) => Promise<void>;
  isLoading?: boolean;
  onCancel?: Function;
  disabled?: boolean;
  additionalButtons?: ReactElement;
};

export const AddComment = (props: tAddComment) => {
  const { onSubmit, isLoading, onCancel, disabled, additionalButtons } = props;
  const ref = useRef<MDXEditorMethods>(null);

  return (
    <div>
      <MarkdownEditor ref={ref} />

      <div className="flex items-center justify-end gap-3 pt-3">
        {additionalButtons && <div className="mr-auto">{additionalButtons}</div>}

        {onCancel && <Button onClick={onCancel}>Cancel</Button>}

        <Button
          onClick={async () => {
            const markdown = ref.current?.getMarkdown();
            if (markdown) await onSubmit(markdown);
          }}
          buttonType={BUTTON_TYPES.MAIN}
          isLoading={isLoading}
          disabled={disabled}>
          Comment
        </Button>
      </div>
    </div>
  );
};
