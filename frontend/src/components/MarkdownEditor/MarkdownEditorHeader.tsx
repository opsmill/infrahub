import React, { FC } from "react";
import { Button } from "../button";

type EditorHeaderProps = {
  preview: boolean;
  onPreviewToggle: Function;
};

export const MarkdownEditorHeader: FC<EditorHeaderProps> = ({ preview, onPreviewToggle }) => (
  <div className="border-b flex justify-between overflow-auto">
    <Button onClick={onPreviewToggle} className="bg-white border-none rounded-none rounded-tl-md">
      {preview ? "Continue editing" : "Preview"}
    </Button>
  </div>
);
