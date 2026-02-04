import { Button } from "@/shared/components/ui/button";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";

type tQuestionMark = {
  className?: string;
  message?: string;
};

export const QuestionMark = ({ className, message }: tQuestionMark) => {
  if (!message) return null;

  return (
    <Tooltip content={message} enabled>
      <Button
        size="icon"
        variant="outline"
        className={classNames("h-4 w-4 p-2 text-[10px]", className)}
        data-cy="question-mark"
      >
        ?
      </Button>
    </Tooltip>
  );
};
