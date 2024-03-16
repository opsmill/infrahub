import { ReactElement } from "react";

type SchemaPageHeaderProps = {
  title: ReactElement | string;
  description?: string;
};
export const SchemaPageHeader = ({ title, description }: SchemaPageHeaderProps) => {
  return (
    <header className="bg-custom-white h-16 border-b flex items-center px-4">
      <h1 className="text-md font-semibold text-gray-900 mr-2 flex items-center gap-2">{title}</h1>
      {description && <p className="text-sm">{description}</p>}
    </header>
  );
};
