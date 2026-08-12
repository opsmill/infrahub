import { Icon } from "@iconify-icon/react";
import React from "react";

import { classNames } from "@/shared/utils/common";

const MAX_TEXT_LENGTH = 200;

interface TextDisplayProps {
  children: string;
  maxChars?: number;
  preventShowMore?: boolean;
}

export const TextDisplay = ({
  children,
  maxChars = MAX_TEXT_LENGTH,
  preventShowMore,
}: TextDisplayProps) => {
  const [showFullText, setShowFullText] = React.useState(false);

  const shouldShowReadMore = children.length > maxChars;
  const shouldTruncateText = shouldShowReadMore && !showFullText;
  const truncatedText = shouldTruncateText ? children.slice(0, maxChars) : children;

  return (
    <div>
      <p className={classNames("break-all", shouldTruncateText && "line-clamp-3")}>
        {truncatedText}
        {shouldTruncateText && "..."}
      </p>
      {shouldShowReadMore && !preventShowMore && (
        <ToggleFullTextButton isFullText={showFullText} setShowFullText={setShowFullText} />
      )}
    </div>
  );
};

interface ToggleFullTextButtonProps {
  isFullText: boolean;
  setShowFullText: (v: boolean) => void;
}

const ToggleFullTextButton = ({ isFullText, setShowFullText }: ToggleFullTextButtonProps) => {
  return (
    <ButtonStyled onClick={() => setShowFullText(!isFullText)} className="flex items-center">
      {isFullText ? "See less" : "See more"}
      <Icon icon={isFullText ? "mdi:minus" : "mdi:plus"} />
    </ButtonStyled>
  );
};

interface ButtonStyledProps extends React.HTMLAttributes<HTMLButtonElement> {
  ref?: React.Ref<HTMLButtonElement>;
}

const ButtonStyled = ({ className, ref, ...props }: ButtonStyledProps) => (
  <button
    ref={ref}
    className={classNames("font-semibold text-custom-blue-700", className)}
    {...props}
  />
);
