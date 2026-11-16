import type React from "react";
import type { FC } from "react";
import { Button } from "react-aria-components";

import { Row } from "@/shared/components/container";
import { Icon } from "@/shared/components/display/icon";
import {
  boldCommand,
  type EditorCommand,
  italicCommand,
  strikethroughCommand,
} from "@/shared/components/editor/commands";
import type { UseCodeMirror } from "@/shared/hooks/useCodeMirror";

type ToolbarProps = { codeMirror: UseCodeMirror };

const ToolBar: FC<ToolbarProps> = ({ codeMirror }) => {
  const handleButtonMouseDown =
    (onClick: EditorCommand["onClick"]) => (event: React.MouseEvent<HTMLButtonElement>) => {
      event.preventDefault();
      if (codeMirror) onClick(codeMirror);
    };

  const commands: EditorCommand[] = [boldCommand, italicCommand, strikethroughCommand];

  return (
    <Row>
      {commands.map(({ label, icon, onClick }) => (
        <Button
          className="inline-flex size-5 shrink-0 items-center justify-center rounded text-lg data-hovered:bg-highlight"
          key={label}
          aria-label={label}
          onMouseDown={handleButtonMouseDown(onClick)}
        >
          <Icon icon={icon} />
        </Button>
      ))}
    </Row>
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
  <Row className="justify-between overflow-auto border-b pr-2">
    <Button
      onClick={onPreviewToggle}
      className="rounded-tl-md px-2 py-1.5 font-semibold text-sm data-hovered:bg-highlight"
    >
      {previewMode ? (editLabel ?? "Continue editing") : (previewLabel ?? "Preview")}
    </Button>

    {!previewMode && <ToolBar codeMirror={codeMirror} />}
  </Row>
);
