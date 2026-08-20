export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "long",
    timeStyle: "short",
  }).format(new Date(iso))
}

/** Compact form for cards/lists — "25 ago · 14:53", no year/weekday. */
export function formatDateShort(iso: string): string {
  const date = new Date(iso)
  const parts = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" }).formatToParts(
    date,
  )
  const day = parts.find((p) => p.type === "day")?.value ?? ""
  const month = (parts.find((p) => p.type === "month")?.value ?? "").replace(".", "")
  const time = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" }).format(date)
  return `${day} ${month} · ${time}`
}

export function formatCurrency(value: string | number): string {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value))
}
