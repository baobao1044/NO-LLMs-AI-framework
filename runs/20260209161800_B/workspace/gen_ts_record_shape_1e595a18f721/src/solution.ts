export function format_row(item: { id: number; name: string }): string {
  return `${item.id}:${item.name}`;
}