import { forwardRef, HTMLAttributes, useState } from "react";
import { classNames } from "../../utils/common";
import { Icon } from "@iconify-icon/react";

const MAX_TEXT_LENGTH = 100;

interface TextDisplayProps {
  children: string;
  maxChars?: number;
}

export const TextDisplay = ({ children, maxChars = MAX_TEXT_LENGTH }: TextDisplayProps) => {
  const [showFullText, setShowFullText] = useState(false);

  const shouldShowReadMore = children.length > maxChars;

  return (
    <div>
      <p className={classNames(!showFullText && "line-clamp-3")}>{children}</p>
      {shouldShowReadMore && (
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

const ButtonStyled = forwardRef<HTMLButtonElement, HTMLAttributes<HTMLButtonElement>>(
  ({ className, ...props }, ref) => (
    <button
      ref={ref}
      className={classNames("text-custom-blue-700 font-semibold", className)}
      {...props}
    />
  )
);
