import { DocumentTextIcon } from "@heroicons/react/24/outline";
import { useEffect, useState } from "react";
import { components } from "../../infraops";
import {
  CONFIG,
  INFRAHUB_API_SERVER_URL,
  INFRAHUB_DOC_URL,
  INFRAHUB_GITHUB_URL,
} from "../../config/config";
import { ReactComponent as GitIcon } from "../../images/icons/git-icon-2.svg";
import { ReactComponent as GraphqlIcon } from "../../images/icons/graphql-icon.svg";
import { ReactComponent as SwaggerIcon } from "../../images/icons/swagger-icon.svg";
import { fetchUrl } from "../../utils/fetch";

const ICONS = [
  {
    component: <GitIcon className="w-4 h-4 fill-custom-blue-50 text-custom-blue-50" />,
    link: INFRAHUB_GITHUB_URL,
  },
  {
    component: <DocumentTextIcon className="w-4 h-4 text-custom-blue-50" />,
    link: INFRAHUB_DOC_URL,
  },
  {
    component: <GraphqlIcon className="w-4 h-4 fill-custom-blue-50 text-custom-blue-50" />,
    link: `${INFRAHUB_API_SERVER_URL}/graphql`,
  },
  {
    component: <SwaggerIcon className="w-4 h-4  fill-custom-blue-50" />,
    link: `${INFRAHUB_API_SERVER_URL}/api/docs`,
  },
];

export const Footer = () => {
  return (
    <div className="bg-custom-white flex items-center p-3">
      <div className="flex space-x-2">
        {ICONS.map((item: any, index: number) => (
          <a
            key={index}
            href={item.link}
            target="_blank"
            rel="noreferrer"
            className="cursor-pointer">
            {item.component}
          </a>
        ))}
      </div>

      <AppVersionInfo />
    </div>
  );
};

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
