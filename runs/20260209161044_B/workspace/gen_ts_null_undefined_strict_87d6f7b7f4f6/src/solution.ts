export function normalize_text(value: string | null | undefined): string {
  return value?.trim() ?? "";
}