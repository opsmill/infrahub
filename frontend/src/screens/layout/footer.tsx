import { DocumentTextIcon } from "@heroicons/react/24/outline";
import { useEffect, useState } from "react";
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
  const [info, setInfo] = useState<any>({});

  const fetchInfo = async () => {
    const result = await fetchUrl(CONFIG.INFO_URL);

    setInfo(result);
  };

  useEffect(() => {
    fetchInfo();
  }, []);

  return (
    <div className="flex items-center border-r border-gray-200">
      <div className="bg-custom-white p-2 flex">
        {ICONS.map((item: any, index: number) => (
          <a
            key={index}
            href={item.link}
            target="_blank"
            rel="noreferrer"
            className="cursor-pointer p-1">
            {item.component}
          </a>
        ))}
      </div>
      <div className="flex-1 text-center text-xs italic text-gray-400 mr-2">
        Version: {info.version}
      </div>
    </div>
  );
};
