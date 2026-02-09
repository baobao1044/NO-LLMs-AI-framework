function pick_user_name(input) {
  return input?.user?.name ?? "";
}

module.exports = {pick_user_name};
