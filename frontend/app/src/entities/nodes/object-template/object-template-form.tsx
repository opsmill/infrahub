import { FileBoxIcon, PlusIcon } from "lucide-react";
import { useState } from "react";
import { Button, type ButtonProps, Dialog, DialogTrigger } from "react-aria-components";

import { Popover } from "@/shared/components/aria/popover";
import ObjectForm, { type ObjectFormProps } from "@/shared/components/form/object-form";
import { classNames } from "@/shared/utils/common";

import { ObjectTemplateAutocomplete } from "@/entities/nodes/object-template/object-template-autocomplete";
import type { NodeObject } from "@/entities/nodes/types";
import type { TemplateSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface StartButtonProps extends ButtonProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  className?: string;
  ref?: React.Ref<HTMLButtonElement>;
}

const StartButton = ({ icon, title, description, className, ...props }: StartButtonProps) => (
  <Button
    className={classNames(
      "flex items-center gap-2 rounded-lg border border-gray-400 border-dashed p-4 hover:bg-gray-50",
      className
    )}
    {...props}
  >
    <div className="rounded-lg bg-indigo-100 p-3">{icon}</div>

    <div className="flex flex-col items-start gap-1">
      <p className="font-medium text-sm">{title}</p>
      <p className="text-gray-600 text-xs">{description}</p>
    </div>
  </Button>
);

const StartFromTemplateButton = ({
  objectTemplateSchema,
  onSelect,
}: {
  objectTemplateSchema: TemplateSchema;
  onSelect: (template: NodeObject | null) => void;
}) => {
  return (
    <DialogTrigger>
      <StartButton
        icon={<FileBoxIcon className="size-6" />}
        title="Start from template"
        description="Pick a premade object and customize it"
      />

      <Popover placement="bottom start" className="w-(--trigger-width)">
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

export interface ObjectTemplateFormProps extends ObjectFormProps {
  objectTemplateKind: string;
}

export default function ObjectTemplateForm({
  objectTemplateKind,
  ...props
}: ObjectTemplateFormProps) {
  const { schema: objectTemplateSchema } = useSchema(objectTemplateKind);
  const [selectedObjectTemplate, setSelectedObjectTemplate] = useState<NodeObject | null>();

  if (!objectTemplateSchema) {
    return `Could not find template schema for ${objectTemplateKind}`;
  }

  if (selectedObjectTemplate !== undefined) {
    return (
      <ObjectForm
        {...props}
        currentProfiles={
          selectedObjectTemplate?.profiles?.edges?.map((edge: any) => edge?.node) ?? []
        }
        objectTemplate={selectedObjectTemplate}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <StartButton
        icon={<PlusIcon className="size-6" />}
        title="Start from scratch"
        description="Create a new blank object"
        onPress={() => setSelectedObjectTemplate(null)}
      />
      <StartFromTemplateButton
        objectTemplateSchema={objectTemplateSchema}
        onSelect={setSelectedObjectTemplate}
      />
    </div>
  );
}
