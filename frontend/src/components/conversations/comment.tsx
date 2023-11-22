import { classNames } from "../../utils/common";
import { AVATAR_SIZE, Avatar } from "../avatar";
import { DateDisplay } from "../date-display";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export const Comment = (props: any) => {
  const { comment, className } = props;

  const createdBy = comment?.created_by?.node?.display_label ?? "Anonymous";
  const createdAt = comment?.created_at?.value;
  const commentContent = comment?.text?.value ?? "";

  return (
    <div className={classNames("p-4 mb-4 text-base bg-white rounded-lg", className)}>
      <div className="flex justify-between items-center mb-2 text-xs">
        <div className="flex items-center w-full">
          <div className="inline-flex items-center mr-3 text-sm text-gray-900 flex-1">
            <Avatar name={createdBy} size={AVATAR_SIZE.SMALL} className="mr-4" />
            {createdBy}
          </div>

          <div className="text-sm text-gray-600">
            <DateDisplay date={createdAt} />
          </div>
        </div>
      </div>

      <Markdown remarkPlugins={[remarkGfm]} className="markdown">
        {commentContent}
      </Markdown>
    </div>
  );
};
