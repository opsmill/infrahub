export const roundNumber = (num: number, digits: number = 2): number => {
  return parseFloat(num.toFixed(digits));
};
