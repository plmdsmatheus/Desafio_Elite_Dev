# Plataforma de Eventos e Ingressos

Organizador publica eventos a partir de um catálogo externo real (Ticketmaster Discovery e
TMDb), cliente reserva, paga (simulado) e recebe um ingresso com QR assinado, e a portaria
valida na entrada por câmera ou código digitado. Disponibilidade de ingressos/assentos
atualiza em tempo real (Server-Sent Events) na tela de quem está comprando.

Desenvolvido para o **Desafio Elite Dev** (Verzel).

## Demo

| | |
|---|---|
| **Frontend** | https://desafio-elite-dev-nine.vercel.app/ |
| **Backend (API)** | https://desafio-elite-dev-6u2i.onrender.com/api/health |
| **Documentação da API** (Swagger) | https://desafio-elite-dev-6u2i.onrender.com/api/docs |

> O backend está no free tier do Render, ele **dorme depois de ~15 min sem tráfego**. A
> primeira requisição depois disso demora uns 30–50s pra "acordar" o container antes de
> responder. Não é bug, é o free tier; um reload(F5) resolve.

## Sumário

- [Funcionalidades](#funcionalidades)
- [Stack técnica](#stack-técnica)
- [Como rodar localmente](#como-rodar-localmente)
- [Dados de teste (seed)](#dados-de-teste-seed)
- [Testes automatizados](#testes-automatizados)
- [Decisões técnicas que valem a leitura](#decisões-técnicas-que-valem-a-leitura)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Limitações conhecidas e o que não foi feito](#limitações-conhecidas-e-o-que-não-foi-feito)
- [Uso de IA](#uso-de-ia)

## Funcionalidades

**Cliente**
- Home (`/`) com banner e carrossel dos próximos eventos disponíveis; busca completa fica em
  `/eventos`, com grid + paginação e filtros que aplicam **instantaneamente** (texto e cidade
  com debounce, categoria/data/toggle na hora), nome do evento/local, cidade (combobox de
  texto livre, sugestões vindas do banco), categoria, data, e um toggle opcional pra mostrar
  esgotados/já realizados (por padrão só aparece o que dá pra comprar agora).
- Detalhe do evento: descrição, organizador, local com mapa (Google Maps embutido) e
  disponibilidade **em tempo real via Server-Sent Events**, o contador de ingressos (ou o mapa
  de assentos, na revisão da compra) atualiza sozinho assim que outra pessoa compra ou solta um
  assento, sem precisar dar refresh.
- Reserva por **quantidade** (pista) ou por **assento específico** (mapa de poltronas, cinema/
  teatro) depende de como o organizador configurou o evento.
- Pagamento simulado, com confirmação e recusa determinísticas (ver seção de dados de teste).
- "Meus ingressos": lista paginada com QR, código público, transferência do ingresso pro e-mail
  de outro cliente cadastrado, e cancelamento com devolução da vaga ao estoque.
- Link de ingresso compartilhável, acessível sem login.

**Organizador**
- Painel com todos os próprios eventos (qualquer status), progresso de vendas por evento.
- Criar/editar evento: manual ou pré-preenchido a partir de uma busca real no catálogo externo
  (Ticketmaster ou TMDb). Liga/desliga mapa de assentos por evento (trava depois de publicado).
- **Ciclo de vida do evento como máquina de estados**, garantida no backend (não só na UI): todo
  evento nasce **rascunho**, tudo editável livremente, invisível pro público, até o organizador
  confirmar a **publicação** como uma ação explícita. Depois de publicado, só dá pra alterar
  data/hora e local, ou **cancelar** o evento (o que invalida automaticamente os ingressos já
  vendidos dele); cancelado é estado terminal.

**Portaria**
- Escolhe o evento da sessão, valida ingressos por **leitura de QR pela câmera** ou por
  **código digitado manualmente** os dois caminhos convergem pro mesmo resultado:
  válido / inválido / já utilizado / evento errado. Histórico da sessão atual na tela.

## Stack técnica

| | |
|---|---|
| **Backend** | Django 6 + Django REST Framework, PostgreSQL, JWT (`djangorestframework-simplejwt`), `drf-spectacular` (schema OpenAPI/Swagger) |
| **Frontend** | React 19 + TypeScript + Vite, Tailwind CSS v4, shadcn/ui (Radix), TanStack Query, `lucide-react` (ícones), `react-day-picker`/`date-fns` (date picker, localizado em pt-BR) |
| **Tempo real** | Server-Sent Events nativo (view em generator, `fetch` no cliente), sem Celery/Channels/Redis, ver seção de decisões técnicas |
| **Integrações externas** | Ticketmaster Discovery API, TMDb API (proxeadas pelo backend a chave nunca chega no navegador) |
| **QR** | Geração: `qrcode.react`. Leitura por câmera: `html5-qrcode`. Assinatura: `django.core.signing` (HMAC) |
| **Deploy** | Vercel (frontend) + Render (backend, Docker, `gunicorn --worker-class gthread`) + Supabase (Postgres) |
| **Local** | Docker Compose (Postgres + backend + frontend com um comando) |

## Como rodar localmente

### Opção 1 — Docker Compose (recomendado)

Pré-requisitos: Docker e Docker Compose.

```bash
git clone https://github.com/plmdsmatheus/Desafio_Elite_Dev.git
cd Desafio_Elite_Dev

cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Abra `backend/.env` e preencha `TICKETMASTER_API_KEY`, `TMDB_API_KEY` e
`TMDB_API_READ_ACCESS_TOKEN` — chaves grátis em:
- https://developer.ticketmaster.com/products-and-docs/apis/getting-started/
- https://developer.themoviedb.org/docs/getting-started

Essas chaves só são usadas pelo organizador pra *buscar* itens reais do catálogo externo na
hora de criar um evento, sem elas o resto da aplicação funciona normalmente, só essa busca
específica fica indisponível.

```bash
docker compose up --build
```

Isso sobe três serviços: `db` (Postgres 17), `backend` (roda `migrate` + `seed_demo_data`
automaticamente + `runserver`) e `frontend` (Vite dev server). Na primeira subida o build
demora um pouco; depois disso é rápido.

- Frontend: http://localhost:5173
- API: http://localhost:8000/api
- Swagger: http://localhost:8000/api/docs
- Django Admin: http://localhost:8000/admin

`seed_demo_data` é **idempotente** pode rodar de novo (reiniciar os containers, por exemplo)
sem duplicar nada nem apagar dados que já existirem.

### Opção 2 — sem Docker

Backend (Python 3.12+, [Poetry](https://python-poetry.org/), Postgres rodando à parte):

```bash
cd backend
cp .env.example .env   # ajuste DATABASE_URL pro seu Postgres local
poetry install
poetry run python manage.py migrate
poetry run python manage.py seed_demo_data
poetry run python manage.py runserver
```

Frontend (Node 20+):

```bash
cd frontend
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000/api
npm install
npm run dev
```

## Dados de teste (seed)

`seed_demo_data` já deixa tudo pronto pra explorar sem montar nada do zero, senha
`demo1234` pra todo mundo:

| Papel | E-mail |
|---|---|
| Organizador | `organizador@demo.com` |
| Cliente | `cliente1@demo.com` |
| Cliente | `cliente2@demo.com` |
| Portaria | `portaria@demo.com` |

O organizador já sai com **14 eventos** publicados (13) e em rascunho (1), com imagens e
sinopses **reais**, apenas 1 fake para testes de visualização no frontend, buscadas de verdade na Ticketmaster e no TMDb na hora de montar o seed, não
inventadas. Quatro deles (dois filmes, dois shows de teatro) já têm mapa de assentos ligado, pra
testar esse fluxo sem precisar criar um evento novo: *Vingadores: Doutor Destino*,
*Batman*, *Wicked (Touring)* e *Dear Evan Hansen*. `cliente1` já sai com 2 ingressos num dos
eventos publicados, um ainda válido e outro já marcado como utilizado, pra testar os dois
estados na portaria sem precisar comprar nada primeiro.

**Pagamento simulado**: qualquer número de cartão aprova, exceto um terminado em `0000`, que é
sempre recusado regra determinística documentada aqui de propósito, pra dar pra testar os
dois fluxos sem depender de sorte.

## Testes automatizados

Backend: 115 testes (`pytest` + `pytest-django`), incluindo testes de **concorrência real**,
threads de verdade com conexões de banco reais, não só o client de testes sequencial do Django, provando que a trava de reserva de assentos e a trava de pagamento seguram sob concorrência
de verdade, não só na teoria e testes das views de SSE que leem só o primeiro chunk do stream
(o payload é emitido antes do primeiro `sleep()` do generator), então nenhum deles espera tempo
real passar.

```bash
cd backend
poetry run pytest
```

Frontend não tem suíte automatizada nesta entrega.
Cada tela foi testada manualmente e também via Playwright pontualmente durante o
desenvolvimento (fluxos completos ponta a ponta contra o backend real, incluindo cenários de
concorrência com múltiplos navegadores/contas simultâneos), mas isso não substitui uma suíte
versionada, ficou como próximo passo natural caso o projeto continue.

## Decisões técnicas que valem a leitura

- **A mesma vaga nunca é vendida duas vezes.** Pra evento por quantidade, a checagem de
  capacidade que vale é a feita *no pagamento*, sob `select_for_update` no evento, a
  checagem na criação da reserva é só uma cortesia de feedback rápido. Pra evento com mapa de
  assentos, a trava é mais forte ainda: cada assento é travado individualmente
  (`select_for_update`, ordenado por id pra não dar deadlock) já na criação da reserva, e um
  hold de 10 minutos impede outra pessoa de reservar o mesmo lugar enquanto o primeiro cliente
  ainda está pagando.
- **Estoque sempre derivado, nunca contado à parte.** `tickets_sold` conta ao vivo os ingressos
  não cancelados, cancelar um ingresso devolve a vaga automaticamente, sem reconciliar um
  contador solto em nenhum lugar.
- **QR não forjável, sem tabela extra.** Assinatura HMAC nativa do Django
  (`django.core.signing`) sobre o código público do ingresso. A portaria aceita tanto o
  payload assinado (lido pela câmera) quanto o código puro (digitado à mão).
- **Sem Celery/cron.** Expiração de hold de assento e o status "evento realizado" são ambos
  computados na leitura (comparação de timestamp), não por um job agendado.
- **Um bug de concorrência real, pego só por causa do teste com threads reais**: a primeira
  versão da trava de assentos usava `select_related` numa consulta com `select_for_update`, o
  Postgres só re-busca a linha travada depois de esperar o lock, então colunas vindas de um
  JOIN na mesma consulta podiam continuar refletindo o snapshot de antes da espera. Um teste
  sequencial nunca teria pego isso. Corrigido buscando os dados relacionados numa consulta
  separada, depois de confirmar o lock.
- **Tempo real sem infra nova.** A mesma filosofia "computado na leitura" se estende pro SSE:
  não tem Celery, Channels nem Redis nesse projeto. A view de disponibilidade é um generator que
  relê o Postgres a cada ~2s e só emite `data:` quando o payload muda, o polling não desaparece,
  só migra do cliente pro servidor e vira push (`: heartbeat` a cada ~15s mantém a conexão viva
  atrás de proxies que fecham conexões ociosas, relevante em produção). Achado ao planejar: um
  `gunicorn` sem `--workers`/`--threads` (1 worker síncrono, o default) deixaria uma única conexão
  SSE aberta travar a API inteira pra todo mundo enquanto ficasse aberta, trocado pro
  `--worker-class gthread` (builtin do próprio gunicorn, sem dependência nova).
- **Ciclo de vida do evento é uma máquina de estados de verdade, não um campo livre.** Criar um
  evento sempre força `status=draft` no backend, não importa o que o cliente mande; publicado só
  aceita mudar data/hora/local ou cancelar (rejeita qualquer outro campo, inclusive "voltar" pra
  rascunho); cancelado rejeita qualquer alteração, mesmo cancelar de novo. Efeito colateral: campos
  como `has_seat_map`, que antes só eram travados na UI, passaram a ser travados de verdade pelo
  backend assim que o evento é publicado.

## Estrutura do repositório

```
backend/
  apps/
    accounts/    # User customizado (organizer/customer/gate), JWT
    catalog/     # Providers Ticketmaster + TMDb (busca proxeada)
    events/      # Event, geração de mapa de assentos
    ticketing/   # Reservation, Payment, Ticket, Seat
  config/        # settings, urls
frontend/
  src/
    api/         # client axios + funções tipadas por domínio
    pages/       # auth, events, checkout, tickets, organizer, gate
    components/  # shadcn/ui + componentes próprios
docker-compose.yml
CHECKPOINTS.md   # log detalhado de todo o processo de desenvolvimento
```

## Limitações conhecidas e o que não foi feito

- **Sem suíte de testes automatizada no frontend** (ver seção de testes acima).
- **Texto da própria interface da câmera de QR em inglês** ("Request Camera Permissions" etc.)
  — vem embutido na biblioteca `html5-qrcode`, que não expõe um hook de i18n no construtor
  público; o resto da tela (labels, mensagens de resultado) está em pt-BR.
- **Recuperação de senha, envio de ingresso por e-mail e nota fiscal não foram implementados**
  — fora do escopo pedido no desafio.
- **Transferência de ingresso** existe (cliente pra cliente, gratuita, só muda o dono). Isso é
  diferente de "revenda entre usuários" (que envolveria cobrança e não foi implementada, também fora do escopo pedido).
- **Sem cache no proxy do catálogo externo** (Redis foi cogitado, ficou de fora, decisão
  consciente de manter a infra simples, ver `CHECKPOINTS.md`). Cada busca do organizador no
  Ticketmaster/TMDb chama a API real na hora; sujeito a rate limit dela em uso intenso.
- **Render free tier dorme após inatividade** e o **Postgres do Supabase free pausa depois de
  ~1 semana sem tráfego**.
- **Faixa etaria dos filmes/shows** só existem em alguns eventos pois implementei depois e os seeds ficaram dando bypass desse recurso.

## Uso de IA

Este projeto foi desenvolvido com **Claude Code** (Anthropic) como par de programação, sessão
por sessão, do esqueleto do backend até os últimos ajustes de UI. `CHECKPOINTS.md` é o log real
do processo, não um resumo escrito depois, mas o histórico incremental de cada etapa, decisão,
bug encontrado e correção, na ordem em que aconteceram, incluindo os becos sem saída (o brilho
que seguia o cursor no card de evento, implementado e depois trocado por uma borda lima a pedido
do usuário; a primeira tentativa de corrigir o `node_modules` isolado do Docker só com
`npm install`, sem o restart do container que faltava) e não só o resultado final.

**O que a IA fez, sob essa direção:** responsável por grande parte da implementação do código a partir das instruções e decisões definidas por mim. Minha atuação permaneceu como direcionador e revisor, intervindo sempre que identificava dificuldades, inconsistências ou divergências em relação ao que havia sido solicitado.

Na etapa inicial do backend, a maior parte do desenvolvimento foi realizada por mim, devido à minha maior familiaridade com essa área. Já no frontend, por possuir menos experiência, enfrentei algumas dificuldades na implementação de telas e comportamentos específicos, o que tornou essa etapa mais demorada. Nesse contexto, deleguei uma parcela maior da implementação à IA, mantendo minha atuação na revisão, validação e correção de eventuais falhas.

Essa abordagem permitiu acelerar significativamente o desenvolvimento do frontend, sem abrir mão do controle sobre as decisões técnicas e da qualidade do código produzido.

## Autor

Matheus Duarte
