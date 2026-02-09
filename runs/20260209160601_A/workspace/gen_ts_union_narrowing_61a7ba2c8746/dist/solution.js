function union_to_number(value) {
  if (typeof value === "string") {
    return Number(value);
  }
  return value;
}

module.exports = {union_to_number};
