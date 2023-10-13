import { BadgeCircle, CIRCLE_BADGE_TYPES } from "./badge-circle";
import { Clipboard } from "./clipboard";

type tId = {
  id: string;
};

export const Id = (props: tId) => {
  const { id } = props;

  return (
    <BadgeCircle type={CIRCLE_BADGE_TYPES.LIGHT}>
      {id} <Clipboard value={id} message="Id copied!" className="ml-2 p-1 rounded-full" />
    </BadgeCircle>
  );
};
