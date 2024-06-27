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
      <div
        className={classNames(
          "rounded-full border bg-custom-white shadow-sm h-4 w-4 text-[10px] text-center cursor-help",
          className
        )}
        data-cy="question-mark">
        ?
      </div>
    </Tooltip>
  );
};
