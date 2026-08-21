import { CardHeader } from "@infrahub/ui";

export const ProposedChangesTableHeader = () => {
  return (
    <CardHeader className="sticky top-px z-10 grid grid-cols-2 px-4 text-center">
      <span className="text-left">Name</span>
      <div className="grid grid-cols-7">
        <span>Reviews</span>
        <span className="col-span-3">Changes</span>
        <span>Checks</span>
        <span className="col-span-2 text-right">Updated</span>
      </div>
    </CardHeader>
  );
};
