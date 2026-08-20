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

## ✅ Checkpoint 6 — Seed de dados de teste

- `apps/accounts/management/commands/seed_demo_data.py` — **idempotente** (usa
  `get_or_create`/`update_or_create`, roda em todo `docker compose up` sem duplicar nada):
  - 1 organizador, 2 clientes, 1 portaria — todos com senha `demo1234`.
  - 4 eventos do organizador: 3 publicados variados de propósito — um "ticketmaster" (show,
    capacidade 100), um "tmdb" (filme, capacidade 60), um "manual" com capacidade **5** (fácil de
    esgotar, bom pra reproduzir a trava de concorrência manualmente) — e 1 **rascunho** (não
    publicado), pra evidenciar a diferença entre `GET /api/organizer/events` (organizador vê tudo)
    e `GET /api/events/` (público, só publicado).
  - 2 ingressos pagos pro cliente 1 no evento principal: **1 já sai validado** (`used`, pra testar
    o estado "já utilizado" sem precisar validar nada manualmente antes) e **1 ainda válido** (pra
    testar a validação de verdade na portaria). O comando imprime os `public_code` dos dois no
    final, pra digitação manual rápida.
  - Removido o override do `command` no `docker-compose.yml` — agora usa o `CMD` do `Dockerfile`
    (`migrate && seed_demo_data && runserver`).
- **Verificado**: rodado 2x seguidas contra o Postgres real — segunda execução não duplicou nada
  (4 usuários, 4 eventos, 1 reserva, 2 tickets, mesmos IDs/códigos nas duas vezes); as 4 senhas
  semeadas autenticam de verdade (`django.contrib.auth.authenticate`) com o papel certo.

## ✅ Checkpoint 7 — Testes de backend

- **52 testes, 91% de cobertura em `apps/`** (`pytest --cov=apps --cov-report=term-missing`).
  Formaliza em suíte permanente tudo que eu vinha validando manualmente via `manage.py shell` nos
  checkpoints anteriores.
- `conftest.py` na raiz do backend com fixtures compartilhadas (`api_client`, `organizer`,
  `customer`, `gate_user`, `published_event`, etc).
- `apps/accounts/tests.py`: registro sempre cria cliente (mesmo se o payload tentar mandar
  `role`), login devolve tokens + dados do usuário, **fluxo real via header `Authorization: Bearer`**
  (não só `force_authenticate`) reproduzindo o que o Swagger UI faz.
- `apps/events/tests.py`: listagem pública só mostra publicados, busca por texto, organizador cria
  /edita o próprio evento, outro organizador leva 404, cliente leva 403, capacidade não pode cair
  abaixo do vendido.
- `apps/catalog/tests.py`: parsing dos dois providers com payloads sintéticos (sem rede), registry
  de providers, e a view com `unittest.mock.patch` no `TMDbProvider.search` (sem chamar API de
  verdade — determinístico, roda em qualquer máquina/CI sem chave configurada).
- `apps/ticketing/tests/` (virou pacote, não um arquivo só — volume grande de casos):
  - `test_signing.py`: roundtrip, assinatura adulterada, entrada aleatória não explode.
  - `test_reservations.py`: soft-check na criação, cartão `...0000` recusa sem gerar ticket, cartão
    normal aprova e gera os tickets certos, não dá pra pagar reserva de outro cliente nem pagar a
    mesma reserva duas vezes.
  - `test_gate.py`: os 4 estados (`valido`/`invalido`/`ja_utilizado`/`evento_errado`), QR
    adulterado, assinatura válida mas pra um código inexistente (não pode passar só por ter boa
    assinatura), digitação manual do `public_code` sem assinatura, cliente não pode validar.
  - `test_concurrency.py` — **a parte que mais importa**: usa `@pytest.mark.django_db(transaction=True)`
    + threads reais (não simuladas) com conexões de banco de fato separadas, formalizando os testes
    de concorrência que eu tinha rodado manualmente: 2 pagamentos simultâneos disputando a última
    vaga (só 1 ganha), 10 pagamentos simultâneos disputando 3 vagas (exatamente 3 ganham), 2
    validações simultâneas do mesmo ingresso na portaria (só 1 dá `valido`, a outra `ja_utilizado`).
    Rodei 3x seguidas pra garantir que não é flaky — estável nas 3.
- `seed_demo_data.py` ficou sem teste automatizado (0% cobertura) — é script de dados, baixo risco,
  e já validei manualmente no Checkpoint 6 (rodei 2x, conferi idempotência e autenticação);
  decisão consciente de não testar, não esquecimento.

## ✅ Checkpoint 7b — Revisão do backend + comentários em inglês

Pedido do usuário antes de seguir pro frontend: revisar todo o backend e trocar os comentários de
português pra inglês, removendo qualquer coisa que soasse mais "narração pra quem está lendo a
sessão" do que comentário de código de verdade.

- **Revisão** (`/code-review high`, 3 agentes de verificação em paralelo): 4 achados confirmados.
  - **Corrigido** — `ReservationPayView` fazia o `get_object_or_404` da `Reservation` *antes* do
    `transaction.atomic()`, sem lock e sem reconferir o status lá dentro. Um duplo POST no mesmo
    pagamento (duplo clique, retry de rede) passava os dois pela checagem de "pending" e o segundo
    estourava em `IntegrityError` não tratado (500) na constraint unique de `Payment.reservation`.
    Agora a `Reservation` é buscada com `select_for_update()` dentro da transação e o status é
    reconferido ali — reserva já paga/recusada responde `409` limpo. Adicionei um teste de
    concorrência de verdade (`test_two_simultaneous_pay_requests_for_the_same_reservation_only_one_succeeds`)
    provando a correção.
  - **Corrigido** — `EventSerializer` expunha `organizer_email` em `GET /api/events/` e
    `GET /api/events/<id>`, ambos públicos e sem autenticação — vazamento de PII pra qualquer
    visitante anônimo. Campo removido (nada no requisito precisa dele).
  - **Corrigido (eficiência)** — `tickets_sold`/`tickets_available` rodavam uma query de agregação
    cada, sem cache, em toda listagem de eventos (até 2N queries extra por página de N eventos).
    Adicionei `Event.objects.with_sold_counts()` (annotate com `Sum` + filtro), usado nas 3
    listagens (`EventListCreateView`, `OrganizerEventListView`, `GateEventListView`); a property
    `tickets_sold` usa a anotação quando disponível e só cai pra query avulsa em buscas de uma
    instância só.
  - **Avaliado e mantido** — o link público de compartilhamento devolve o mesmo `qr_payload`
    assinado que valida o ingresso na portaria, não uma visão só-leitura. Decisão deliberada: o
    requisito é "compartilhar um ingresso via link", e o sentido de compartilhar um ingresso é o
    destinatário poder usá-lo — é assim que compartilhamento de ingresso funciona no mundo real
    (a pessoa manda o link/QR, quem recebe entra com ele). Documentado aqui pra não ser lido como
    descuido.
- **Comentários e docstrings do código traduzidos de PT-BR pra inglês** em todo `backend/apps/` e
  `backend/config/` — só o que é comentário de desenvolvedor (`#`, docstrings). Textos que são
  produto (mensagens de erro da API, `help_text`/`summary`/`description` do Swagger, labels de
  `TextChoices`, conteúdo do seed) continuam em português de propósito — é o idioma da aplicação
  pros usuários finais, não comentário de código.
- Suíte inteira (53 testes) + `manage.py check` + `manage.py spectacular --fail-on-warn` +
  `makemigrations --check` rodados de novo depois de tudo — tudo limpo.

## 📌 Item de polimento (fim do projeto) — Cache de catálogo com Redis

Decisão com o usuário: Redis como cache do `CatalogSearchView` (evitar rate limit do Ticketmaster/TMDb) é
aditivo e isolado — fica pra polimento final, depois do frontend funcionando ponta a ponta (dica
do próprio enunciado: básico completo antes de agregar valor).

## ✅ Checkpoint 8 — Esqueleto do frontend

Dividido a pedido do usuário: só o esqueleto aqui (tooling + estrutura + build funcionando);
telas/features reais, auth context de verdade e identidade visual própria ficam pro Checkpoint 9.

- **Toolchain**: não havia Node.js disponível neste sandbox nem `apt`/`nvm` — baixei o binário
  oficial (Node 24 LTS) direto de nodejs.org e linkei em `~/.local/bin` (mesmo padrão usado pro
  Poetry no Checkpoint 1).
- **Vite + React + TS** (`npm create vite@latest -- --template react-ts`), **Tailwind CSS v4**
  (`@tailwindcss/vite`, sem `tailwind.config` — CSS-first) e **shadcn/ui** (CLI nova versão,
  preset "nova"/Radix — tema default por enquanto, identidade visual própria fica pro Checkpoint 9
  quando as telas de verdade existirem pra dar contexto de design).
  Alias `@/*` configurado (`tsconfig` + `vite.config.ts`).
- **Estrutura de pastas**: `src/api/` (cliente axios com refresh de JWT automático em 401 — só a
  infra, sem endpoints específicos ainda), `src/pages/{auth,events,organizer,checkout,tickets,gate}/`
  (uma página placeholder por rota, real o suficiente pra provar que o roteamento funciona),
  `src/hooks/`, `src/lib/` (query client do TanStack Query), `src/types/` (tipos TS espelhando os
  serializers do backend).
- **Roteamento**: `react-router-dom`, todas as rotas planejadas já mapeadas em `App.tsx`
  (`/`, `/eventos/:id`, `/login`, `/cadastro`, `/checkout/:id`, `/meus-ingressos`, `/t/:shareSlug` —
  mesmo padrão de link que o backend gera —, `/organizador`, `/organizador/eventos/novo`,
  `/organizador/eventos/:id/editar`, `/portaria`).
- `Dockerfile` do frontend (dev server do Vite, `--host 0.0.0.0`) + serviço `frontend` no
  `docker-compose.yml` (volume anônimo em `/app/node_modules` pra não deixar o bind mount do host
  sobrescrever o `node_modules` instalado dentro do container).
- **Verificado de verdade**: `npm run build` e `npm run lint` limpos (só 1 warning esperado em
  código gerado pelo shadcn). Baixei Chromium via Playwright (sem `apt`/root disponíveis, precisei
  do binário direto) pra tirar screenshot real do dev server rodando — roteamento confirmado
  visualmente em duas rotas diferentes, Tailwind/shadcn aplicados, fonte Geist carregando, zero
  erros de console.
- Não consegui testar o `docker compose up` do frontend dentro deste sandbox (mesma limitação de
  `docker` ausente já registrada nos checkpoints anteriores) — precisa de validação do usuário.

## ⬜ Checkpoint 9 — Telas do frontend

Dividido a pedido do usuário: uma tela por vez, com pausa pra personalização entre cada uma. Ordem
combinada: **fundação** (auth) → login/cadastro → lista de eventos → detalhe do evento →
reserva+pagamento → meus ingressos (QR) → ingresso compartilhado → painel do organizador →
criar/editar evento → portaria.

### ✅ 9.1 — Fundação de auth + Login/Cadastro

- **`useAuth()`** (`src/hooks/use-auth.ts`) — decisão de design: em vez de Context+Provider, o
  usuário logado vive no cache do TanStack Query sob a chave `["me"]`. Todo componente que chama
  `useAuth()` compartilha o mesmo dado automaticamente (dedupe nativo do React Query), sem precisar
  envolver a árvore num `<AuthProvider>`. Ao carregar a página, se houver token salvo, busca
  `GET /api/auth/me` pra restaurar a sessão (token não é confiado no client sem essa checagem); se
  falhar, limpa o token. Escolhi essa abordagem depois que o `oxlint` acusou dois warnings reais no
  design inicial com `useEffect`+`useState` manual (`set-state-in-effect` e
  `only-export-components`) — o redesenho eliminou os dois warnings e o código ficou mais simples.
- **`src/api/client.ts`**: instância do axios com refresh automático de JWT em 401 — mas
  excluindo explicitamente os próprios endpoints de auth (`login`/`register`/`refresh`) dessa
  lógica, porque um 401 *deles* significa "credencial errada", não "sessão expirada" (achei esse
  bug ao testar de verdade: sem a exclusão, a mensagem de erro real do backend era mascarada por
  uma tentativa de refresh fadada ao fracasso).
- **`Layout`** (`src/components/layout.tsx`): header com nav que muda conforme o papel logado
  (organizador → "Meus eventos", cliente → "Meus ingressos", portaria → "Portaria"), envolve todas
  as rotas via `<Outlet />`.
- **`LoginPage`/`RegisterPage`**: formulários controlados (sem `react-hook-form`, mantido simples),
  cadastro sempre cria cliente (sem seletor de papel — espelha a decisão do backend, com uma nota
  explicando isso na tela), cadastro loga automaticamente em seguida (reserva não pede duas vezes
  as mesmas credenciais). Erros da API normalizados por `src/lib/api-error.ts`.
- **Correção no backend**: `EmailTokenObtainPairSerializer` tinha a mensagem padrão do
  `django-rest-framework-simplejwt` em inglês ("No active account found...") vazando pra API —
  sobrescrita para "E-mail ou senha inválidos." (achado durante o teste real do fluxo, não estava
  nos checkpoints anteriores porque não tínhamos frontend consumindo esse erro ainda).
- **Verificado de ponta a ponta com Playwright de verdade** (não só build/lint): cadastro → login
  automático → header mostra e-mail → logout → login manual com as mesmas credenciais → sessão
  sobrevive a reload de página (prova que o `GET /auth/me` de restauração funciona) → senha errada
  mostra "E-mail ou senha inválidos." em vermelho. Zero erros de console (fora o 401 esperado do
  teste de senha errada). Usei o `docker compose up` que o usuário já tinha rodando (backend na
  porta 8000, frontend na 5173) em vez de subir servidores próprios — bind mount + HMR já refletiam
  o código novo. Usuários de teste (`_pw_test_*`) removidos do banco depois.

### ✅ 9.1b — Identidade visual (paleta de cores)

Usuário não gostou da paleta cinza monocromática padrão do shadcn e pediu uma paleta própria:
`#08121A` `#0F2D3A` `#1E6F7D` `#7BC6C9` `#E7F3F2` (petróleo/teal, do quase-preto ao branco-menta).

- Reescrevi `src/index.css`: os 5 tons viram variáveis nomeadas (`--brand-950` a `--brand-50`), e
  todos os tokens do shadcn (`background`, `primary`, `card`, `border`, `chart-*`, `sidebar-*` etc)
  são derivados só a partir desses 5 — tons intermediários usam `color-mix()` do CSS (ex.:
  `color-mix(in oklch, var(--brand-300) 18%, white)`) em vez de inventar cores novas fora da
  paleta. Funciona tanto no tema claro quanto no escuro (`.dark`).
- **Claro**: fundo branco-menta, cards brancos, botão primário no teal médio, texto navy escuro.
- **Escuro**: fundo navy quase-preto, cards no tom petróleo escuro (nível acima do fundo), botão
  primário no teal claro (contraste alto sobre fundo escuro).
- **Verificado visualmente com Playwright** nos dois modos (claro e forçando a classe `.dark`) nas
  telas de login/cadastro, incluindo o estado de erro (vermelho ainda legível nos dois fundos).
  `npm run build`/`lint` seguem limpos.

### ✅ 9.1c — Ajustes de UX pedidos pelo usuário

- **Espaçamento do card**: menos padding no topo (`pt-8` → `pt-4`/`pt-6`), card mais largo
  (`max-w-sm` → `max-w-md`).
- **Mostrar senha**: `src/components/password-input.tsx` — input com ícone de olho (lucide-react)
  que alterna `type="password"`/`"text"`, usado em login/cadastro (senha e confirmar senha).
- **Erros por campo, não perto do botão**: `getApiFieldErrors()` em `src/lib/api-error.ts` separa
  a resposta de erro da API por campo (`{"email": [...]}` → `{email: "..."}`); cada input tem seu
  próprio slot de erro logo abaixo (`aria-invalid` + borda vermelha do próprio shadcn). No login, o
  erro de credencial inválida (que não pertence a um campo específico) fica anexado à senha — é o
  padrão mais comum desse tipo de formulário. Mantive a validação nativa do navegador
  (`required`/`type=email`) pros casos óbvios, sem `noValidate`.
- **Estado ativo no header**: troquei `Link` por `NavLink` do react-router — o link da página atual
  fica com `font-medium text-foreground`, os demais em `text-muted-foreground`.
- **Bug real de responsividade corrigido**: reproduzi o problema que o usuário descreveu — no
  header logado, em telas estreitas (320px), o e-mail empurrava o botão "Sair" pra fora da tela
  (nenhum wrap, sem overflow visível pro usuário). Corrigido com `flex-wrap` no header (nav quebra
  pra segunda linha se não couber) e ocultando o e-mail abaixo do breakpoint `sm` (não é informação
  essencial no mobile, o papel + "Sair" já bastam).
- **Verificado com Playwright** em 3 larguras (1280px, 375px, 320px), logado e deslogado, com
  screenshot antes/depois confirmando o bug de overflow e a correção.

## ⬜ Checkpoint 10 — README e documentação de uso de IA

- Passo a passo de setup/execução, credenciais de teste semeadas, limitações conhecidas, seção
  transparente de uso de IA (o que foi feito com IA nesta sessão vs. o que o usuário lapidou por
  conta própria — principalmente identidade visual e ajustes finos de UX).
