import { classNames } from "../utils/common";

export enum AVATAR_SIZE {
  SMALL,
}
interface tAvatar {
  name: string;
  image?: string;
  className?: string;
  size?: AVATAR_SIZE;
}

export const initials = (name: string) =>
  name
    ? name
        .split(" ")
        .map((word) => word[0])
        .join("")
        .toUpperCase()
    : "-";

const getAvatarSize = (size?: AVATAR_SIZE) => {
  switch (size) {
    case AVATAR_SIZE.SMALL: {
      return "h-8 w-8 text-xs";
    }
    default: {
      return "h-12 w-12";
    }
  }
};

export const Avatar = (props: tAvatar) => {
  const { name, image, size, className, ...otherProps } = props;

  if (image) {
    return (
      <img
        className={`${getAvatarSize(size)} rounded-full object-cover`}
        src={image}
        alt="Avatar"
        {...otherProps}
      />
    );
  } else {
    return (
      <div
        className={classNames(
          getAvatarSize(size),
          "rounded-full bg-custom-blue-200 text-custom-white flex justify-center items-center",
          className ?? ""
        )}
        {...otherProps}>
        {initials(name)}
      </div>
    );
  }
};
