interface Props {
  image?: string;
  name: string;
}

export const Avatar = (props: Props) => {
  const { name, image } = props;

  const initials = name
    .split(" ")
    .map((word) => word[0])
    .join("")
    .toUpperCase();

  if (image) {
    return <img className={"h-12 w-12 rounded-full object-cover"} src={image} alt="Avatar" />;
  } else {
    return (
      <div
        className={
          "h-12 w-12 rounded-full bg-custom-gray text-custom-white flex justify-center items-center"
        }>
        {initials}
      </div>
    );
  }
};
