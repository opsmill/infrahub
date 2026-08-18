import { CloudUploadIcon, FileUpIcon } from "lucide-react";
import {
  Button,
  DropZone,
  type DropZoneProps,
  FileTrigger,
  type FileTriggerProps,
  isFileDropItem,
} from "react-aria-components";

import { disabledStyle, focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { Col } from "@/shared/components/container";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export interface FileDropzoneProps extends DropZoneProps {
  onFileSelect: (file: File) => void;
}

export function FileDropzone({ onFileSelect, className, ...props }: FileDropzoneProps) {
  const handleDrop: DropZoneProps["onDrop"] = async (e) => {
    const fileItem = e.items.find(isFileDropItem);
    if (fileItem) {
      const file = await fileItem.getFile();
      onFileSelect(file);
    }
  };

  const handleSelect: FileTriggerProps["onSelect"] = (files) => {
    const file = files?.[0];
    if (file) {
      onFileSelect(file);
    }
  };

  return (
    <DropZone
      onDrop={handleDrop}
      render={(domProps, { isDropTarget, ...renderProps }) => (
        <div {...domProps}>
          <FileTrigger onSelect={handleSelect}>
            <Button
              {...renderProps}
              className={classNames(
                inputStyle,
                disabledStyle,
                focusVisibleStyle,
                "size-full h-38 justify-center",
                isDropTarget && "border-ring bg-highlight",
                className
              )}
            >
              {isDropTarget ? <DropzoneActiveContent /> : <DropzoneIdleContent />}
            </Button>
          </FileTrigger>
        </div>
      )}
      {...props}
    />
  );
}

function DropzoneIdleContent() {
  return (
    <Col className="items-center">
      <CloudUploadIcon className="size-9 text-subtle-muted" />
      <Col className="gap-0.5">
        <p className="text-sm text-subtle">Drag and drop a file here, or click to select</p>
        <p className="text-subtle-muted text-xs">PDF, YAML, JSON, TXT, CSV, images, and more</p>
        <p className="text-subtle-muted text-xs">Max file size: 10MB</p>
      </Col>
    </Col>
  );
}

function DropzoneActiveContent() {
  return (
    <Col className="items-center">
      <FileUpIcon className="size-6 text-custom-blue-500" />
      <p className="text-sm text-subtle">Drop the file here...</p>
    </Col>
  );
}
