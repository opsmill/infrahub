import { Icon } from "@iconify-icon/react";
import React, { FC } from "react";
import { UseCodeMirror } from "../../hooks/useCodeMirror";
import { Button } from "../buttons/button";
import { boldCommand, EditorCommand, italicCommand, strikethroughCommand } from "./commands";

type ToolbarProps = { codeMirror: UseCodeMirror };

const ToolBar: FC<ToolbarProps> = ({ codeMirror }) => {
  const handleButtonMouseDown =
    (onClick: EditorCommand["onClick"]) => (event: React.MouseEvent<HTMLButtonElement>) => {
      event.preventDefault();
      if (codeMirror) onClick(codeMirror);
    };

  const commands: EditorCommand[] = [boldCommand, italicCommand, strikethroughCommand];

  return (
    <div className="flex items-center gap-2 pr-2">
      {commands.map(({ label, icon, onClick }) => (
        <Button
          key={label} // Using the label as a key for uniqueness
          className="bg-white border-none p-0 text-xl shadow-none"
          type="button"
          aria-label={label}
          onMouseDown={handleButtonMouseDown(onClick)}>
          <Icon icon={icon} />
        </Button>
      ))}
    </div>
  );
};

type EditorHeaderProps = {
  codeMirror: UseCodeMirror;
  previewMode: boolean;
  onPreviewToggle: () => void;
};

export const MarkdownEditorHeader: FC<EditorHeaderProps> = ({
  codeMirror,
  previewMode,
  onPreviewToggle,
}) => (
  <div className="border-b flex justify-between overflow-auto">
    <Button onClick={onPreviewToggle} className="bg-white border-none rounded-none rounded-tl-md">
      {previewMode ? "Continue editing" : "Preview"}
    </Button>

    {!previewMode && <ToolBar codeMirror={codeMirror} />}
  </div>
);
