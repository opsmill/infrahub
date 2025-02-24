import { ObjectTemplateAutocomplete } from "@/entities/nodes/object-template/object-template-autocomplete";
import { NodeObject } from "@/entities/nodes/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { Popover } from "@/shared/components/aria/popover";
import ObjectForm, { ObjectFormProps } from "@/shared/components/form/object-form";
import { FileBoxIcon, PlusIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button, Dialog, DialogTrigger } from "react-aria-components";

export interface ObjectTemplateFormProps extends ObjectFormProps {
  objectTemplateKind: string;
}

const StartFromScratchButton = ({ onPress }: { onPress: () => void }) => (
  <Button
    onPress={onPress}
    className="flex items-center gap-2 border border-dashed border-gray-400 p-4 rounded-lg hover:bg-gray-50"
  >
    <div className="bg-indigo-100 rounded-lg p-3">
      <PlusIcon className="size-6" />
    </div>

    <div className="flex flex-col items-start gap-1">
      <p className="text-sm font-medium">Start from scratch</p>
      <p className="text-xs text-gray-600">Create a new blank object</p>
    </div>
  </Button>
);

const StartFromTemplateButton = ({
  objectTemplateSchema,
  onSelect,
}: {
  objectTemplateSchema: any;
  onSelect: (template: NodeObject | null) => void;
}) => {
  let buttonRef = useRef<HTMLButtonElement>(null);
  let [buttonWidth, setButtonWidth] = useState<string | null>(null);
  useEffect(() => {
    if (buttonRef.current) {
      setButtonWidth(buttonRef.current.offsetWidth + "px");
    }
  }, [buttonRef]);

  return (
    <DialogTrigger>
      <Button
        ref={buttonRef}
        className="flex items-center gap-2 border border-dashed border-gray-400 p-4 rounded-lg hover:bg-gray-50 relative"
      >
        <div className="bg-indigo-100 rounded-lg p-3">
          <FileBoxIcon className="size-6" />
        </div>

        <div className="flex flex-col items-start gap-1">
          <p className="text-sm font-medium">Start from template</p>
          <p className="text-xs text-gray-600">Pick a premade object and customize it</p>
        </div>
      </Button>

      <Popover style={buttonWidth ? { width: buttonWidth } : undefined} placement="bottom start">
        <Dialog>
          <ObjectTemplateAutocomplete
            autoFocus
            templateSchema={objectTemplateSchema}
            onSelect={onSelect}
          />
        </Dialog>
      </Popover>
    </DialogTrigger>
  );
};

export default function ObjectTemplateForm({
  objectTemplateKind,
  ...props
}: ObjectTemplateFormProps) {
  const { schema: objectTemplateSchema } = useSchema(objectTemplateKind);
  const [currentObjectTemplate, setCurrentObjectTemplate] = useState<NodeObject | null>();

  if (!objectTemplateSchema) {
    return `Could not find template schema for ${objectTemplateKind}`;
  }

  if (currentObjectTemplate !== undefined) {
    return <ObjectForm {...props} objectTemplate={currentObjectTemplate} />;
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <StartFromScratchButton onPress={() => setCurrentObjectTemplate(null)} />
      <StartFromTemplateButton
        objectTemplateSchema={objectTemplateSchema}
        onSelect={setCurrentObjectTemplate}
      />
    </div>
  );
}
