import { NavLink, Outlet, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/hooks/use-auth"
import { cn } from "@/lib/utils"
import type { UserRole } from "@/types"

const ROLE_LINK: Record<UserRole, { to: string; label: string }> = {
  organizer: { to: "/organizador", label: "Meus eventos" },
  customer: { to: "/meus-ingressos", label: "Meus ingressos" },
  gate: { to: "/portaria", label: "Portaria" },
}

const navLinkClassName = ({ isActive }: { isActive: boolean }) =>
  cn(
    "transition-colors hover:text-foreground",
    isActive ? "font-medium text-foreground" : "text-muted-foreground",
  )

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate("/")
  }

  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3">
          <NavLink to="/" className="shrink-0 font-semibold">
            Plataforma de Eventos
          </NavLink>

          <nav className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            {user ? (
              <>
                <NavLink to={ROLE_LINK[user.role].to} className={navLinkClassName}>
                  {ROLE_LINK[user.role].label}
                </NavLink>
                <span className="hidden text-muted-foreground sm:inline">{user.email}</span>
                <Button variant="outline" size="sm" onClick={handleLogout}>
                  Sair
                </Button>
              </>
            ) : (
              <>
                <NavLink to="/login" className={navLinkClassName}>
                  Entrar
                </NavLink>
                <Button asChild size="sm">
                  <NavLink to="/cadastro">Criar conta</NavLink>
                </Button>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
