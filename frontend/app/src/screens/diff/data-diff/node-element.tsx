import { DiffNodeProperty } from "./node-property";

type DiffNodeElementProps = {
  element: any;
};

export const DiffNodeElement = ({ element }: DiffNodeElementProps) => {
  console.log("element: ", element);

  return (
    <div>
      {element.properties.map((property, index) => (
        <DiffNodeProperty key={index} property={property} />
      ))}
    </div>
  );
};
