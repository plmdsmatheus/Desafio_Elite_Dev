import { ptBR } from "date-fns/locale"
import { CalendarIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

/** Parses a "YYYY-MM-DD" value into a local-time Date (midnight) — building
 * the date from its numeric parts instead of `new Date(isoString)`, which
 * parses a bare date as UTC midnight and can render as the previous day
 * once formatted back in a timezone behind UTC. */
function parseISODate(value: string): Date | undefined {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return undefined
  const [, year, month, day] = match
  return new Date(Number(year), Number(month) - 1, Number(day))
}

function toISODate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

interface DatePickerProps {
  id?: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}

/** Date-only picker (no time) backed by shadcn's Calendar+Popover, exchanging
 * plain "YYYY-MM-DD" strings — the same format the native
 * `<input type="date">` it replaces already produced, so call sites (e.g. the
 * event search filter) didn't need to change how they read/send the value. */
export function DatePicker({ id, value, onChange, placeholder = "Selecione uma data", className }: DatePickerProps) {
  const selected = value ? parseISODate(value) : undefined

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          className={cn(
            "w-full justify-start gap-2 font-normal",
            !selected && "text-muted-foreground",
            className,
          )}
        >
          <CalendarIcon className="size-4 shrink-0" />
          {selected
            ? new Intl.DateTimeFormat("pt-BR", { dateStyle: "long" }).format(selected)
            : placeholder}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0">
        <Calendar
          mode="single"
          selected={selected}
          onSelect={(date) => onChange(date ? toISODate(date) : "")}
          locale={ptBR}
          autoFocus
        />
      </PopoverContent>
    </Popover>
  )
}
