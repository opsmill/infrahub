import type React from "react";

import { Avatar } from "@/shared/components/display/avatar";
import { DateDisplay } from "@/shared/components/display/date-display";
import { MarkdownRender } from "@/shared/components/editor/markdown/markdown-render";
import { classNames } from "@/shared/utils/common";

type CommentProps = {
  author: string;
  createdAt: Date;
  content: string;
  className?: string;
};
export const Comment: React.FC<CommentProps> = ({ author, createdAt, content, className = "" }) => {
  return (
    <div
      className={classNames("rounded-lg bg-white p-2 text-base", className)}
      data-testid="comment"
    >
      <div className="mb-2 flex items-center justify-between text-xs">
        <div className="flex w-full items-center">
          <div className="mr-3 inline-flex flex-1 items-center text-gray-900 text-sm">
            <Avatar name={author} size={"sm"} className="mr-4" />
            {author}
          </div>

          <div className="text-gray-600 text-sm">
            <DateDisplay date={createdAt} />
          </div>
        </div>
      </div>

      <MarkdownRender markdownText={content} />
    </div>
  );
};
