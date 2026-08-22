import { ptBR } from "date-fns/locale"
import { CalendarIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

/** Splits a "YYYY-MM-DDTHH:mm" value (the same shape `<input
 * type="datetime-local">` already produced) into a local Date for the
 * calendar and a "HH:mm" string for the time field — built from the numeric
 * parts, not `new Date(isoString)`, since a datetime-local string has no
 * timezone and should read as-is, not get UTC-shifted. */
function parseValue(value: string): { date: Date | undefined; time: string } {
  const [datePart, timePart] = value.split("T")
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(datePart ?? "")
  if (!match) return { date: undefined, time: timePart ?? "" }
  const [, year, month, day] = match
  return { date: new Date(Number(year), Number(month) - 1, Number(day)), time: timePart ?? "" }
}

function toValue(date: Date, time: string): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  const datePart = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
  return `${datePart}T${time || "00:00"}`
}

interface DateTimePickerProps {
  id?: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
  "aria-invalid"?: boolean
}

/** Date+time picker backed by shadcn's Calendar+Popover plus a native time
 * input for the hour/minute part (shadcn has no separate time-picker
 * primitive — a plain `<input type="time">` inside the popover is the
 * standard pattern). Exchanges the same "YYYY-MM-DDTHH:mm" string
 * `<input type="datetime-local">` already used, so callers didn't need to
 * change how they read/send the value. */
export function DateTimePicker({
  id,
  value,
  onChange,
  placeholder = "Selecione data e hora",
  className,
  "aria-invalid": ariaInvalid,
}: DateTimePickerProps) {
  const { date: selected, time } = parseValue(value)

  function handleDateSelect(date: Date | undefined) {
    if (!date) return
    onChange(toValue(date, time || "00:00"))
  }

  function handleTimeChange(newTime: string) {
    onChange(toValue(selected ?? new Date(), newTime))
  }

  const label = selected
    ? `${new Intl.DateTimeFormat("pt-BR", { dateStyle: "long" }).format(selected)}${time ? ` às ${time}` : ""}`
    : placeholder

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          aria-invalid={ariaInvalid}
          className={cn(
            "w-full justify-start gap-2 font-normal",
            !selected && "text-muted-foreground",
            className,
          )}
        >
          <CalendarIcon className="size-4 shrink-0" />
          <span className="truncate">{label}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0">
        <Calendar mode="single" selected={selected} onSelect={handleDateSelect} locale={ptBR} autoFocus />
        <div className="flex items-center gap-2 border-t p-3">
          <Label htmlFor={id ? `${id}-time` : undefined} className="text-sm text-muted-foreground">
            Hora
          </Label>
          <Input
            id={id ? `${id}-time` : undefined}
            type="time"
            value={time}
            onChange={(e) => handleTimeChange(e.target.value)}
            className="w-fit"
          />
        </div>
      </PopoverContent>
    </Popover>
  )
}
