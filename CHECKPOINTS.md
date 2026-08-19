# Checkpoints — Plataforma de Eventos e Ingressos

Acompanhamento do progresso do desafio, para retomar o contexto entre sessões sem reler tudo.
A arquitetura completa (modelo de dados, API, decisões de concorrência/QR) está detalhada no
plano original salvo em `/home/matheus-ubuntu/.claude/plans/giggly-bouncing-kernighan.md`.

## Decisões fechadas com o usuário

- Stack: Django (DRF) + PostgreSQL · React + Vite + TS · Tailwind + shadcn/ui.
- Gerenciador de pacotes Python: **Poetry** (não pip/requirements.txt).
- Catálogo externo: **Ticketmaster Discovery + TMDb** (as duas).
- Reserva: começar só por **quantidade (pista)**; mapa de assentos fica pra depois, se sobrar tempo.
- Deploy: só local via **Docker Compose** (sem deploy em nuvem por ora).
- Postgres do Compose publicado em `5433` no host (evita colidir com um Postgres local do usuário
  já ocupando a 5432; internamente o backend sempre fala com `db:5432`).

## ✅ Checkpoint 1 — Esqueleto do backend

- Projeto Django (`backend/config`) com 4 apps em `backend/apps/`: `accounts`, `catalog`,
  `events`, `ticketing`.
- Dependências via Poetry (`pyproject.toml` + `poetry.lock`): Django 6.1, DRF, SimpleJWT,
  django-environ, django-cors-headers, psycopg2-binary, requests; dev: pytest + pytest-django.
- `apps.accounts`: `User` customizado (login por e-mail, `role`: organizer/customer/gate) +
  migration inicial. Endpoints: `POST /api/auth/register` (sempre cria cliente),
  `POST /api/auth/login` (JWT, já devolve dados do usuário), `POST /api/auth/refresh`,
  `GET /api/auth/me`. Permissions por papel prontas (`IsOrganizer`, `IsCustomer`, `IsGate`) em
  `apps/accounts/permissions.py`, para reutilizar nas próximas apps.
- Settings 100% via `.env` (`django-environ`), `DATABASE_URL` único, CORS liberado pro Vite,
  `pt-br` / `America/Sao_Paulo`.
- `backend/Dockerfile` pronto (build com Poetry, `POETRY_VIRTUALENVS_CREATE=false`).
- `.gitignore` raiz cobrindo Python, Node e `.env`.

## ✅ Checkpoint 2 — Postgres via Docker Compose

- `docker-compose.yml` na raiz: serviço `db` (postgres:17-alpine, volume nomeado, healthcheck,
  porta `5433:5432`) + serviço `backend` (builda o Dockerfile, `depends_on` com
  `condition: service_healthy`, override do `DATABASE_URL` pra rede interna do Compose, volume
  `./backend:/app` pra hot-reload em dev).
- `command` do serviço `backend` no Compose está temporariamente só com `migrate` + `runserver`
  (sem seed ainda — `seed_demo_data` entra no Checkpoint 6). O `Dockerfile` já tem o `CMD` "final"
  com seed incluído; quando o management command existir, dá pra remover o override do Compose.
- **Testado e confirmado rodando pelo usuário** (`docker compose up`) — não consegui validar
  Docker dentro do sandbox desta sessão (sem `docker` disponível aqui), só validei a sintaxe do
  YAML manualmente.

## ✅ Checkpoint 3 — Modelos de `events` e `ticketing`

- `Event` (organizer FK, source_provider/source_id, título, descrição, imagem, categoria
  show/movie, venue/endereço/cidade, data, capacidade, preço, status draft/published/canceled) +
  properties `tickets_sold`/`tickets_available` (import local de `ticketing` pra evitar ciclo de
  módulos entre as duas apps).
- `Reservation` (event/customer FK, quantity, status pending/paid/declined/canceled, total_price),
  `Payment` (OneToOne com Reservation, status approved/declined, só guarda os últimos 4 dígitos do
  "cartão" simulado — regra de recusa determinística entra no Checkpoint 5), `Ticket`
  (reservation FK + event FK denormalizado, `public_code` de 10 chars sem caracteres ambíguos pra
  digitação manual, `share_slug` UUID pro link público, status valid/used/canceled).
- Admin registrado para as duas apps (`autocomplete_fields`, inlines de Payment/Ticket dentro de
  Reservation).
- Migrations geradas e **aplicadas de verdade** contra o Postgres do Docker Compose (a porta 5433
  ainda estava acessível de dentro do sandbox — `migrate` rodou limpo, `showmigrations` confirma
  as 3 apps aplicadas).
- A trava de concorrência em si (`transaction.atomic()` + `select_for_update()` no `Event`, na
  aprovação do pagamento) ainda não existe — é lógica de view, entra no Checkpoint 5.

## ⬜ Checkpoint 4 — Catálogo externo (Ticketmaster + TMDb)

- `apps/catalog/providers/`: `TicketmasterProvider` e `TMDbProvider` com interface comum
  `search(query)`. Endpoint `GET /api/catalog/search?provider=...&q=...` (só organizador).
- Chaves via `.env` (`TICKETMASTER_API_KEY`, `TMDB_API_KEY`), nunca expostas ao frontend.

## ⬜ Checkpoint 5 — Endpoints de events/reservations/payment/tickets/gate

- CRUD de eventos pelo organizador + listagem/busca pública.
- Reserva por quantidade, pagamento simulado, emissão de tickets com QR assinado
  (`django.core.signing`), endpoint público de ticket compartilhado, validação na portaria com os
  4 estados (`valido`/`invalido`/`ja_utilizado`/`evento_errado`).

## ⬜ Checkpoint 6 — Seed de dados de teste

- Management command `seed_demo_data`: 1 organizador, 2 clientes, 1 portaria, ao menos 1 evento
  publicado com ingressos disponíveis. Depois disso, tirar o override do `command` no
  `docker-compose.yml`.

## ⬜ Checkpoint 7 — Testes de backend

- `pytest-django`: reserva concorrente não estoura capacidade, assinatura do QR rejeita payload
  adulterado, ticket não valida duas vezes, pagamento aprova/recusa conforme regra.

## ⬜ Checkpoint 8 — Scaffold do frontend

- Vite + React + TS, Tailwind, shadcn/ui (com identidade visual própria, não o tema default),
  estrutura de pastas (`api/`, `pages/`, `components/`, `hooks/`, `lib/`, `types/`), axios +
  TanStack Query, auth context com guard de rotas por papel, `Dockerfile` do frontend + serviço no
  Compose.

## ⬜ Checkpoint 9 — Telas do frontend

Ordem sugerida: auth → navegação/busca de eventos → criação de evento (organizador) →
reserva + pagamento simulado → "Meus ingressos" com QR (`qrcode.react`) → portaria (câmera via
`html5-qrcode` + digitação manual).

## ⬜ Checkpoint 10 — README e documentação de uso de IA

- Passo a passo de setup/execução, credenciais de teste semeadas, limitações conhecidas, seção
  transparente de uso de IA (o que foi feito com IA nesta sessão vs. o que o usuário lapidou por
  conta própria — principalmente identidade visual e ajustes finos de UX).
