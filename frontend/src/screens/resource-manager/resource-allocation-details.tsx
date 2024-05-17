import { useParams } from "react-router-dom";

const ResourceAllocationDetails = () => {
  const { resourceId } = useParams();
  return <div>Resource {resourceId}</div>;
};

export default ResourceAllocationDetails;
