export function pick_user_name(input: { user?: { name?: string } } | null): string {
  return input.user.name;
}
