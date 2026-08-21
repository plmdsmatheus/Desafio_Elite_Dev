import { useState } from "react"
import { Link, Navigate, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PasswordInput } from "@/components/password-input"
import { useAuth } from "@/hooks/use-auth"
import { getApiFieldErrors } from "@/lib/api-error"
import type { UserRole } from "@/types"

const ROLE_HOME: Record<UserRole, string> = {
  organizer: "/organizador",
  customer: "/",
  gate: "/portaria",
}

interface FieldErrors {
  email?: string
  password?: string
}

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (user) {
    return <Navigate to={ROLE_HOME[user.role]} replace />
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setFieldErrors({})
    setIsSubmitting(true)
    try {
      const loggedInUser = await login(email, password)
      navigate(ROLE_HOME[loggedInUser.role])
    } catch (err) {
      const errors = getApiFieldErrors(err)
      // Login only ever fails with a generic "invalid credentials" — there's no
      // way to know which of the two fields is wrong, so it's shown under the
      // password field (closest to the button, last thing the user typed).
      setFieldErrors({ ...errors, password: errors.password ?? "E-mail ou senha inválidos." })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex justify-center pt-4 sm:pt-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Entrar</CardTitle>
          <CardDescription>Acesse sua conta de cliente e organizador.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">E-mail</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                aria-invalid={!!fieldErrors.email}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
              {fieldErrors.email && (
                <p className="text-xs text-destructive">{fieldErrors.email}</p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Senha</Label>
              <PasswordInput
                id="password"
                autoComplete="current-password"
                required
                aria-invalid={!!fieldErrors.password}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              {fieldErrors.password && (
                <p className="text-xs text-destructive">{fieldErrors.password}</p>
              )}
            </div>

            <Button type="submit" disabled={isSubmitting} className="mt-2">
              {isSubmitting ? "Entrando..." : "Entrar"}
            </Button>

            <p className="text-center text-sm text-muted-foreground">
              Não tem conta?{" "}
              <Link to="/cadastro" className="text-foreground underline underline-offset-4">
                Criar conta
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
