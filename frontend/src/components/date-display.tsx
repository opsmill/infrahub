import { format, formatDistanceToNow } from "date-fns";

type DateDisplayProps = {
  date?: number | string | Date;
  hideDefault?: boolean;
  fromNow?: boolean;
}

export const DateDisplay = (props: DateDisplayProps) => {
  const { date, hideDefault, fromNow } = props;

  if (!date && hideDefault) {
    return null;
  }

  return (
    <span className="mr-2 italic font-normal">
      {
        fromNow
          ? formatDistanceToNow(props.date ? new Date() : new Date(), { addSuffix: true })
          : format(props.date ? new Date() : new Date(), "MM/dd/yyy HH:mm")
      }
    </span>
  );

};