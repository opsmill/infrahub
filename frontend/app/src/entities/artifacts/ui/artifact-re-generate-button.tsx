import { CONFIG } from "@/config/config";
import { QSP } from "@/config/qsp";
import { useAuth } from "@/entities/authentication/ui/useAuth";
import { queryClient } from "@/shared/api/rest/client";
import { fetchUrl, getUrlWithQsp } from "@/shared/api/rest/fetch";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { classNames } from "@/shared/utils/common";
import { RefreshCwIcon } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";

type tGenerateProps = {
  label?: string;
  artifactid?: string;
  definitionid?: string;
};

export const ArtifactReGenerateButton = (props: tGenerateProps) => {
  const { label, artifactid, definitionid } = props;

  const { objectid } = useParams();
  const auth = useAuth();

  const [branch] = useQueryParam(QSP.BRANCH, StringParam);
  const [at] = useQueryParam(QSP.DATETIME, StringParam);
  const [isLoading, setIsLoading] = useState(false);

  const { isAuthenticated } = useAuth();

  const handleGenerate = async () => {
    try {
      setIsLoading(true);

      const url = CONFIG.ARTIFACTS_GENERATE_URL(definitionid || objectid);

      const options: string[][] = [
        ["branch", branch ?? ""],
        ["at", at ?? ""],
      ].filter(([, v]) => v !== undefined && v !== "");

      const urlWithQsp = getUrlWithQsp(url, options);

      const res = await fetchUrl(urlWithQsp, {
        method: "POST",
        headers: {
          authorization: `Bearer ${auth.accessToken}`,
        },
        ...(artifactid ? { body: JSON.stringify({ nodes: [artifactid] }) } : {}),
      });

      if (res?.errors?.length) {
        throw new Error("Error while generating artifact");
      }

      await queryClient.invalidateQueries({ queryKey: ["is-task-running"] });

      if (artifactid) {
        toast(<Alert message="Artifact re-generated" type={ALERT_TYPES.SUCCESS} />);
      } else {
        toast(<Alert message="Artifacts generated" type={ALERT_TYPES.SUCCESS} />);
      }

      setIsLoading(false);
    } catch (error) {
      console.error("Error when generating artifacts: ", error);

      setIsLoading(false);
      toast(
        <Alert message="An error occured while generating the artifact" type={ALERT_TYPES.ERROR} />
      );
    }
  };

  return (
    <Button variant={"active"} disabled={!isAuthenticated || isLoading} onClick={handleGenerate}>
      <RefreshCwIcon className={classNames("mr-2 size-4", isLoading && "animate-spin")} />
      {label ?? "Generate"}
    </Button>
  );
};
