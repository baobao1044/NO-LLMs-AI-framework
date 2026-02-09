export function union_to_number(value: string | number): number {
  if (typeof value === "string") {
    return Number(value);
  }
  return value;
}
