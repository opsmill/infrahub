import { useRunGeneratorMutation } from "@/entities/generators/domain/run-generator.mutation";
import { Button, ButtonProps } from "@/shared/components/buttons/button-primitive";
import { RefreshCwIcon } from "lucide-react";

export interface TriggerGeneratorButtonProps extends ButtonProps {
  generatorId: string;
  targetNodeIds?: string[];
}

export function RunGeneratorButton({
  generatorId,
  targetNodeIds,
  children,
  ...props
}: TriggerGeneratorButtonProps) {
  const { isPending, mutate } = useRunGeneratorMutation();

  return (
    <Button
      isLoading={isPending}
      disabled={isPending}
      variant="active"
      onClick={() => mutate({ generatorId, targetNodeIds })}
      {...props}
    >
      {!isPending && <RefreshCwIcon className="size-4 mr-2" />}
      {children ?? "Generate"}
    </Button>
  );
}
