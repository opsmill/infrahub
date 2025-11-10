import { Icon } from "@iconify-icon/react";
import type React from "react";
import type { FC } from "react";

import { Button } from "@/shared/components/buttons/button";
import type { UseCodeMirror } from "@/shared/hooks/useCodeMirror";

import { boldCommand, type EditorCommand, italicCommand, strikethroughCommand } from "../commands";

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
          className="border-none bg-white p-0 text-xl shadow-none"
          type="button"
          aria-label={label}
          onMouseDown={handleButtonMouseDown(onClick)}
        >
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
  editLabel?: string;
  previewLabel?: string;
};

export const MarkdownEditorHeader: FC<EditorHeaderProps> = ({
  codeMirror,
  previewMode,
  onPreviewToggle,
  editLabel,
  previewLabel,
}) => (
  <div className="flex justify-between overflow-auto border-gray-200 border-b">
    <Button onClick={onPreviewToggle} className="rounded-none rounded-tl-md border-none bg-white">
      {previewMode ? (editLabel ?? "Continue editing") : (previewLabel ?? "Preview")}
    </Button>

    {!previewMode && <ToolBar codeMirror={codeMirror} />}
  </div>
);
