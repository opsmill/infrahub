export const formatNumberDisplay = (num: number): string => {
  return Intl.NumberFormat("en-EN").format(num);
};
