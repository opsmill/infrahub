export const ProposedChangesTableHeader = () => {
  return (
    <div className="sticky top-0 grid grid-cols-2 bg-gray-50 px-4 py-2 text-center text-sm">
      <span className="text-left">Name</span>
      <div className="grid grid-cols-7">
        <span>Reviews</span>
        <span className="col-span-3">Changes</span>
        <span>Checks</span>
        <span className="col-span-2 text-right">Updated</span>
      </div>
    </div>
  );
};
