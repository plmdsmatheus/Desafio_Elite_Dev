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

## ✅ Checkpoint 4 — Catálogo externo (Ticketmaster + TMDb)

- `apps/catalog/providers/`: `CatalogItem` (dataclass normalizado) + `CatalogProvider` (interface
  `search(query)`), `TicketmasterProvider` e `TMDbProvider` implementando ela. Registry em
  `providers/__init__.py` (`get_provider(key)`).
- TMDb usa Bearer token (`TMDB_API_READ_ACCESS_TOKEN`, v4 auth) se configurado, senão cai pro
  `?api_key=` (v3). Ticketmaster sempre mapeia pra `category="show"`, TMDb pra `"movie"`.
- Endpoint `GET /api/catalog/search?provider=ticketmaster|tmdb&q=...`, só organizador
  (`IsOrganizer`). Erros de config/provider inválido/sem query → 400 com mensagem clara; erro de
  rede na API externa → 502. Chaves nunca saem do backend.
- **Verificado sem chave de API real** (não tenho acesso à internet neste sandbox pra chamada
  ao vivo): parsing dos dois providers testado com payloads sintéticos no formato documentado das
  APIs (evento completo, filme completo, evento com campos faltando) — todos os campos mapeados
  corretamente, nenhum crash em dados ausentes. View testada com `APIRequestFactory` cobrindo os 4
  casos: sem chave configurada (400), provider inválido (400), sem `q` (400), cliente tentando
  acessar (403).
- **Testado ao vivo** depois que o usuário colocou as chaves reais no `.env` (corrigi um espaço em
  branco a mais que o `django-environ` não removeu sozinho e quebraria a autenticação nas APIs):
  busca real "Coldplay" no Ticketmaster (20 resultados) e "Duna"/"Matrix" no TMDb (20 resultados,
  via Bearer token v4) passando pela `CatalogSearchView` completa — permissão, serialização e
  conversão de timezone (`America/Sao_Paulo`) tudo correto.

## ✅ Checkpoint 5 — Endpoints de events/reservations/payment/tickets/gate

- **Events**: `GET/POST /api/events/` (lista pública com filtros `q`/`city`/`category`/`date` +
  criação pelo organizador), `GET/PATCH /api/events/<id>` (leitura pública de publicados — ou do
  próprio rascunho — e edição restrita ao dono), `GET /api/organizer/events` (lista própria com
  `tickets_sold`/`tickets_available`). Posse é resolvida via `get_queryset` (quem não é dono recebe
  404, não 403 — não vaza que o evento existe). Reduzir `capacity` abaixo do já vendido é bloqueado
  na validação do serializer.
- **Reservations/Payment**: `POST /api/reservations` (soft-check de disponibilidade, não é a fonte
  da verdade), `POST /api/reservations/<id>/pay` — **aqui mora a trava de concorrência real**:
  `transaction.atomic()` + `select_for_update()` no `Event`, recontagem de `tickets_sold` dentro do
  lock, só then decide aprovar/recusar. Regra de recusa determinística: cartão terminado em `0000`.
- **Tickets**: `GET /api/tickets/mine`, `GET /api/tickets/<share_slug>/public` (sem login). QR
  assinado via `apps/ticketing/signing.py` (`django.core.signing`, salt dedicado).
- **Gate**: `GET /api/gate/events` (sessões disponíveis), `POST /api/gate/validate` — aceita tanto
  o payload assinado do QR quanto o `public_code` digitado à mão, sempre responde 200 com
  `result` ∈ `valido`/`invalido`/`ja_utilizado`/`evento_errado`, e também usa `select_for_update`
  no `Ticket` pra não permitir duas validações simultâneas da mesma corrida.
- `APPEND_SLASH = False` nas settings (URLs da API não usam barra final; evita redirect 301
  quebrando POST/PATCH).
- **Verificado com testes de integração reais contra o Postgres** (via `manage.py shell`, limpando
  os dados no final): fluxo completo organizador→cliente→portaria; **teste de concorrência de
  verdade com threads** — dois clientes pagando ao mesmo tempo por um evento de capacidade 1: só 1
  aprovado, só 1 ticket emitido; QR válido → `ja_utilizado` na segunda leitura → `evento_errado` em
  outro evento → `invalido` com assinatura adulterada; pagamento recusado (cartão `...0000`) não
  gera ticket; edição de evento por dono (200) vs. outro organizador (404) vs. cliente (403);
  bloqueio de reduzir capacidade abaixo do vendido (400). Tudo passou, banco limpo depois.

## ✅ Checkpoint 5b — Documentação interativa da API (Swagger/OpenAPI)

Não estava no PDF, mas vale a pena tanto pra visualização quanto pra teste manual — decisão do
usuário, não do enunciado.

- `drf-spectacular` (schema OpenAPI 3) + `drf-spectacular-sidecar` (assets do Swagger UI/ReDoc
  servidos localmente via staticfiles, sem depender de CDN — combina com a decisão de deploy só
  local via Docker Compose).
- Rotas: `GET /api/schema` (JSON/YAML cru), `GET /api/docs` (Swagger UI, interativo — dá pra clicar
  em "Authorize" e colar o `access` token pra testar endpoints protegidos direto no navegador),
  `GET /api/redoc` (ReDoc, leitura).
- Todas as views anotadas com `@extend_schema`/`@extend_schema_view` (tags por domínio: auth,
  catalog, events, reservations, tickets, gate) — inclusive as `APIView` "opacas" que não tinham
  `serializer_class` (`ReservationPayView`, `GateValidateView`, `CatalogSearchView`, `MeView`),
  usando serializers dedicados só pra documentação (`PaymentResultSerializer`,
  `GateValidateResultSerializer`) que descrevem a resposta real sem interferir na lógica.
- Os `TextChoices` de status/papel (que eram classes aninhadas nos models) viraram classes de
  módulo (`EventStatus`, `ReservationStatus`, `UserRole`, etc.) com um alias na classe do model
  (`Event.Status = EventStatus`) pra manter o código igual em todo lugar — necessário pro
  `ENUM_NAME_OVERRIDES` do drf-spectacular conseguir importar cada choices e gerar nomes de enum
  legíveis no schema (sem isso, viravam `Status361Enum` etc. por colisão de nome). Não gerou
  migration nova (choices não afeta o schema do banco).
- **Verificado**: `manage.py spectacular --fail-on-warn` gera o schema sem nenhum warning/erro (14
  paths, 17 operações, todas taggeadas corretamente); JWT Bearer detectado automaticamente como
  security scheme (`jwtAuth`), sem precisar de extensão custom; assets do Swagger UI confirmados
  servindo localmente (200, sem CDN); fluxo completo testado via HTTP de verdade contra o
  `runserver` (não só chamadas em processo) — registro → login → `GET /api/auth/me` com Bearer
  token → 401 sem token — exatamente o caminho que alguém percorre clicando em "Authorize" no
  Swagger.

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
