export const roundNumber = (num: number, digits: number = 2): number => {
  return parseFloat(num.toFixed(digits));
};

export const formatNumberDisplay = (num: number): string => {
  return Intl.NumberFormat("en-EN").format(num);
};
