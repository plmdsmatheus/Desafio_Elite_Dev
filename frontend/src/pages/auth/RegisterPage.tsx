import { useState } from "react"
import { Link, Navigate, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PasswordInput } from "@/components/password-input"
import { useAuth } from "@/hooks/use-auth"
import { getApiFieldErrors } from "@/lib/api-error"

interface FieldErrors {
  email?: string
  password?: string
  confirmPassword?: string
}

export function RegisterPage() {
  const { user, register } = useAuth()
  const navigate = useNavigate()

  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (user) {
    return <Navigate to="/" replace />
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setFieldErrors({})

    if (password !== confirmPassword) {
      setFieldErrors({ confirmPassword: "As senhas não coincidem." })
      return
    }

    setIsSubmitting(true)
    try {
      await register({ email, password, first_name: firstName, last_name: lastName })
      navigate("/")
    } catch (err) {
      const errors = getApiFieldErrors(err)
      setFieldErrors(Object.keys(errors).length > 0 ? errors : { email: "Não foi possível criar a conta." })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex justify-center pt-4 sm:pt-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Criar conta</CardTitle>
          <CardDescription>Cadastre-se para reservar sessões e comprar ingressos.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="first_name">Nome</Label>
                <Input
                  id="first_name"
                  autoComplete="given-name"
                  value={firstName}
                  onChange={(event) => setFirstName(event.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="last_name">Sobrenome</Label>
                <Input
                  id="last_name"
                  autoComplete="family-name"
                  value={lastName}
                  onChange={(event) => setLastName(event.target.value)}
                />
              </div>
            </div>

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
                autoComplete="new-password"
                minLength={8}
                required
                aria-invalid={!!fieldErrors.password}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              {fieldErrors.password && (
                <p className="text-xs text-destructive">{fieldErrors.password}</p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="confirm_password">Confirmar senha</Label>
              <PasswordInput
                id="confirm_password"
                autoComplete="new-password"
                minLength={8}
                required
                aria-invalid={!!fieldErrors.confirmPassword}
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
              />
              {fieldErrors.confirmPassword && (
                <p className="text-xs text-destructive">{fieldErrors.confirmPassword}</p>
              )}
            </div>

            <Button type="submit" disabled={isSubmitting} className="mt-2">
              {isSubmitting ? "Criando conta..." : "Criar conta"}
            </Button>

            <p className="text-center text-sm text-muted-foreground">
              Já tem conta?{" "}
              <Link to="/login" className="text-foreground underline underline-offset-4">
                Entrar
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
