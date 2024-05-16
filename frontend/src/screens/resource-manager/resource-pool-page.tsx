import { useParams } from "react-router-dom";
import Content from "../layout/content";

const ResourcePoolPage = () => {
  const { resourcePoolId } = useParams();
  return <Content>Resource pool {resourcePoolId}</Content>;
};

export default ResourcePoolPage;
