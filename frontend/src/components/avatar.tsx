import { useState } from "react";

interface Props {
  image?: string;
  name: string;
}

const getRandomColor = () => {
  let colors = ["#0283ba", "#e1242c", "#01c7d4", "#a55aa8", "#ffbc79"];
  const randomIndex = Math.floor(Math.random() * colors.length);
  let randomColor = colors[randomIndex];
  return randomColor;
};

export const Avatar = (props: Props) => {
  const { name, image } = props;
  const [bgColor] = useState(getRandomColor());
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
        style={{
          background: bgColor,
        }}
        className={
          "h-12 w-12 rounded-full bg-gray-700 text-white flex justify-center items-center"
        }>
        {initials}
      </div>
    );
  }
};
