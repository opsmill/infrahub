import { DiffNodeProperty } from "./node-property";

type DiffNodeElementProps = {
  element: any;
};

export const DiffNodeElement = ({ element }: DiffNodeElementProps) => {
  return (
    <div>
      {element.properties
        .filter((property) => property.status !== "UNCHANGED")
        .map((property, index) => (
          <DiffNodeProperty key={index} property={property} />
        ))}
    </div>
  );
};
