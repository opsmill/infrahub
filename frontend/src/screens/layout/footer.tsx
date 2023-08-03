import { DocumentTextIcon } from "@heroicons/react/24/outline";
import { INFRAHUB_API_SERVER_URL, INFRAHUB_DOC_URL } from "../../config/config";
import { ReactComponent as GitIcon } from "../../images/icons/git-icon-2.svg";
import { ReactComponent as GraphqlIcon } from "../../images/icons/graphql-icon.svg";
import { ReactComponent as SwaggerIcon } from "../../images/icons/swagger-icon.svg";

const ICONS = [
  {
    component: <GitIcon className="w-4 h-4 fill-custom-blue-50 text-custom-blue-50" />,
    link: `${INFRAHUB_API_SERVER_URL}/graphql`,
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
    link: `${INFRAHUB_API_SERVER_URL}/docs`,
  },
];

export const Footer = () => {
  return (
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
  );
};
