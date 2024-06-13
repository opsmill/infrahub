import { Tooltip } from "@/components/ui/tooltip";
import { Button } from "@/components/buttons/button-primitive";

type tQuestionMark = {
  message?: string;
};

export const QuestionMark = ({ message }: tQuestionMark) => {
  if (!message) return null;

  return (
    <Tooltip content={message} enabled>
      <Button
        size="icon"
        variant="outline"
        className="h-4 w-4 p-2 text-[10px]"
        data-cy="question-mark">
        ?
      </Button>
    </Tooltip>
  );
};
