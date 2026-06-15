import { Button, Tooltip } from "@infrahub/ui";

import { classNames } from "@/shared/utils/common";

type tQuestionMark = {
  className?: string;
  message?: string;
};

export const QuestionMark = ({ className, message }: tQuestionMark) => {
  if (!message) return null;

  return (
    <Tooltip message={message}>
      <Button
        size="xs"
        shape="circle"
        variant="outline"
        className={classNames("h-4 w-4 p-2 text-[10px]", className)}
        data-cy="question-mark"
      >
        ?
      </Button>
    </Tooltip>
  );
};
