import { useGenerateArtifactMutation } from "@/entities/artifacts/domain/generate-artifact.mutation";
import { useAuth } from "@/entities/authentication/ui/useAuth";
import { queryClient } from "@/shared/api/rest/client";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { classNames } from "@/shared/utils/common";
import { RefreshCwIcon } from "lucide-react";
import { toast } from "react-toastify";

type ArtifactGenerateButtonProps = {
  label?: string;
  artifactId?: string;
  artifactDefinitionId: string;
};

export const ArtifactGenerateButton = (props: ArtifactGenerateButtonProps) => {
  const { label, artifactId, artifactDefinitionId } = props;
  const { isPending, mutate } = useGenerateArtifactMutation();

  const { isAuthenticated } = useAuth();

  const handleGenerate = () => {
    mutate(
      {
        artifactDefinitionId,
        ...(artifactId ? { nodeIds: [artifactId] } : {}),
      },
      {
        onSuccess: async () => {
          await queryClient.invalidateQueries({ queryKey: ["is-task-running"] });

          if (artifactId) {
            toast(<Alert message="Artifact re-generated" type={ALERT_TYPES.SUCCESS} />);
          } else {
            toast(<Alert message="Artifacts generated" type={ALERT_TYPES.SUCCESS} />);
          }
        },
        onError: (error) => {
          console.error("Error when generating artifacts: ", error);

          toast(
            <Alert
              message="An error occured while generating the artifact"
              type={ALERT_TYPES.ERROR}
            />
          );
        },
      }
    );
  };

  return (
    <Button variant="active" disabled={!isAuthenticated || isPending} onClick={handleGenerate}>
      <RefreshCwIcon className={classNames("mr-2 size-4", isPending && "animate-spin")} />
      {label ?? "Generate"}
    </Button>
  );
};
