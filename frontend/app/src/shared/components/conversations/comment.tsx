import { Avatar } from "@/shared/components/display/avatar";
import { DateDisplay } from "@/shared/components/display/date-display";
import { MarkdownRender } from "@/shared/components/editor/markdown/markdown-render";
import { classNames } from "@/shared/utils/common";
import React from "react";

type CommentProps = {
  author: string;
  createdAt: Date;
  content: string;
  className?: string;
};
export const Comment: React.FC<CommentProps> = ({ author, createdAt, content, className = "" }) => {
  return (
    <div
      className={classNames("p-2 text-base bg-white rounded-lg", className)}
      data-testid="comment"
    >
      <div className="flex justify-between items-center mb-2 text-xs">
        <div className="flex items-center w-full">
          <div className="inline-flex items-center mr-3 text-sm text-gray-900 flex-1">
            <Avatar name={author} size={"sm"} className="mr-4" />
            {author}
          </div>

          <div className="text-sm text-gray-600">
            <DateDisplay date={createdAt} />
          </div>
        </div>
      </div>

      <MarkdownRender markdownText={content} />
    </div>
  );
};
