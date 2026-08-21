import { useQueryClient } from "@tanstack/react-query"
import { Send } from "lucide-react"
import { useState } from "react"
import { transferTicket } from "@/api/tickets"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { getApiErrorMessage } from "@/lib/api-error"
import type { Ticket } from "@/types"

interface TransferTicketDialogProps {
  ticket: Ticket
}

export function TransferTicketDialog({ ticket }: TransferTicketDialogProps) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [email, setEmail] = useState("")
  const [error, setError] = useState("")
  const [success, setSuccess] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function handleOpenChange(nextOpen: boolean) {
    setOpen(nextOpen)
    if (!nextOpen) {
      setEmail("")
      setError("")
      setSuccess(false)
    }
  }

  async function handleSubmit(formEvent: React.FormEvent) {
    formEvent.preventDefault()
    setError("")
    setIsSubmitting(true)
    try {
      await transferTicket(ticket.id, email)
      setSuccess(true)
      await queryClient.invalidateQueries({ queryKey: ["my-tickets"] })
    } catch (err) {
      setError(getApiErrorMessage(err, "Não foi possível transferir o ingresso."))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm" className="shrink-0">
          <Send />
          Enviar para outra pessoa
        </Button>
      </DialogTrigger>
      <DialogContent>
        {success ? (
          <>
            <DialogHeader>
              <DialogTitle>Ingresso enviado!</DialogTitle>
              <DialogDescription>
                O ingresso agora pertence a <strong>{email}</strong> e não aparece mais na sua
                lista de ingressos.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button type="button" onClick={() => handleOpenChange(false)}>
                Fechar
              </Button>
            </DialogFooter>
          </>
        ) : (
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle>Enviar ingresso</DialogTitle>
              <DialogDescription>
                Informe o e-mail de outra pessoa já cadastrada na plataforma. O ingresso passa a
                ser dela e some da sua lista.
              </DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-2 py-2">
              <Label htmlFor={`transfer-email-${ticket.id}`}>E-mail do destinatário</Label>
              <Input
                id={`transfer-email-${ticket.id}`}
                type="email"
                required
                autoFocus
                placeholder="pessoa@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              {error && <p className="text-sm text-destructive">{error}</p>}
            </div>
            <DialogFooter>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Enviando..." : "Enviar ingresso"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
