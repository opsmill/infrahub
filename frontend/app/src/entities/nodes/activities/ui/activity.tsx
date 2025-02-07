import { EventNodeInterface, NodeMutatedEvent } from "@/shared/api/graphql/generated/graphql";

export type ActivityType = EventNodeInterface | NodeMutatedEvent;

export const Activity = ({
  id,
  event,
  occurred_at,
  account_id,
  branch,
  ...props
}: ActivityType) => {
  if ("attributes" in props) {
    console.log("props.attributes: ", props.attributes);
  }

  return <div>{id}</div>;
};
