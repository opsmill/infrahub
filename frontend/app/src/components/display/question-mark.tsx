import { Button } from "@/components/buttons/button-primitive";
import { Tooltip } from "@/components/ui/tooltip";
import { classNames } from "@/utils/common";

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
