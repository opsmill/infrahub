import { Button } from "@/components/buttons/button-primitive";
import { Tooltip } from "@/components/ui/tooltip";
import {
  CONFIG,
  INFRAHUB_API_SERVER_URL,
  INFRAHUB_DOC_LOCAL,
  INFRAHUB_GITHUB_URL,
} from "@/config/config";
import { constructPath, fetchUrl } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { components } from "../../infraops";

const AppVersionInfo = () => {
  const [info, setInfo] = useState<components["schemas"]["InfoAPI"] | null>(null);

  const fetchInfo = async () => {
    const result: components["schemas"]["InfoAPI"] = await fetchUrl(CONFIG.INFO_URL);

    setInfo(result);
  };

  useEffect(() => {
    fetchInfo();
  }, []);

  if (!info) return null;
  return <div className="flex-grow text-right text-xs text-gray-400">version {info.version}</div>;
};

export const Footer = () => {
  return (
    <div className="bg-custom-white flex items-center p-3">
      <div className="flex space-x-2 text-custom-blue-50">
        <Tooltip content="Git repository" side="top" enabled>
          <a href={INFRAHUB_GITHUB_URL} target="_blank" rel="noreferrer">
            <Button variant="ghost" size="icon">
              <Icon icon="mdi:git" className="text-xl" />
            </Button>
          </a>
        </Tooltip>

        <Tooltip content="Infrahub documentation" side="top" enabled>
          <a href={INFRAHUB_DOC_LOCAL} target="_blank" rel="noreferrer">
            <Button variant="ghost" size="icon">
              <Icon icon="mdi:file-document" className="text-xl" />
            </Button>
          </a>
        </Tooltip>

        <Tooltip content="GraphQL sandbox" side="top" enabled>
          <Link to={constructPath("/graphql")}>
            <Button variant="ghost" size="icon">
              <Icon icon="mdi:graphql" className="text-xl" />
            </Button>
          </Link>
        </Tooltip>

        <Tooltip content="Swagger documentation" side="top" enabled>
          <a href={`${INFRAHUB_API_SERVER_URL}/api/docs`} target="_blank" rel="noreferrer">
            <Button variant="ghost" size="icon">
              <Icon icon="mdi:code-json" className="text-xl" />
            </Button>
          </a>
        </Tooltip>
      </div>

      <AppVersionInfo />
    </div>
  );
};
