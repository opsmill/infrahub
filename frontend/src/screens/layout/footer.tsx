import { Icon } from "@iconify-icon/react";
import { useEffect, useState } from "react";
import { Tooltip } from "../../components/ui/tooltip";
import {
  CONFIG,
  INFRAHUB_API_SERVER_URL,
  INFRAHUB_DOC_URL,
  INFRAHUB_GITHUB_URL,
} from "../../config/config";
import { components } from "../../infraops";
import { fetchUrl } from "../../utils/fetch";

const ICONS = [
  {
    component: <Icon icon="mdi:git" className="text-3xl text-custom-blue-50" />,
    link: INFRAHUB_GITHUB_URL,
    content: "OK",
  },
  {
    component: <Icon icon="mdi:file-document" className="text-3xl text-custom-blue-50" />,
    link: INFRAHUB_DOC_URL,
    content: "OK",
  },
  {
    component: <Icon icon="mdi:graphql" className="text-3xl text-custom-blue-50" />,
    link: `${INFRAHUB_API_SERVER_URL}/graphql`,
    content: "OK",
  },
  {
    component: <Icon icon="mdi:code-json" className="text-3xl text-custom-blue-50" />,
    link: `${INFRAHUB_API_SERVER_URL}/api/docs`,
    content: "OK",
  },
];

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
      <div className="flex space-x-2">
        {ICONS.map((item: any, index: number) => {
          console.log("item.content: ", item.content);
          return (
            <Tooltip key={index} content={item.content}>
              <a
                href={item.link}
                target="_blank"
                rel="noreferrer"
                className="flex items-center cursor-pointer">
                {item.component}
              </a>
            </Tooltip>
          );
        })}
      </div>

      <AppVersionInfo />
    </div>
  );
};
