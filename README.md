# 🏆 Chores & Rewards

Rodinná webová aplikace pro správu domácích úkolů a vyplácení odměn v bitcoinu (satoshi).

Dítě plní úkoly → rodič schválí → sats se automaticky pošlou na Lightning peněženku dítěte.

---

## Funkce

- 👦 **Dětský pohled** – přehled úkolů, odesílání splnění, history odměn
- 👨‍👧 **Rodičovský panel** – správa dětí, úkolů, schvalování splnění, vyplácení
- ⚡ **Lightning platby** – výplata přes Lightning Address nebo Bitlifi (tel. číslo / alias)
- 📊 **Historie** – přehled všech výplat a splněných úkolů
- 🔒 **PIN ochrana** – rodičovský panel chráněný PINem s lockoutem

---

## Požadavky

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / Mac / Linux)
- Účet na [LNbits](https://lnbits.com/) instanci (vlastní nebo veřejná, např. `lnbits.cz`)
- Git (volitelně – nebo stáhni ZIP ze záložky Code → Download ZIP)

---

## Instalace a spuštění

### 1. Stáhni projekt

```bash
git clone https://github.com/zirky/chores-rewards.git
cd chores-rewards
```

Nebo stáhni jako ZIP a rozbal.

### 2. Vytvoř konfigurační soubor

Zkopíruj vzorový soubor a vyplň hodnoty:

```bash
# Linux / Mac
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

Otevři `.env` v textovém editoru a vyplň:

```env
LNBITS_URL=https://lnbits.cz          # URL tvé LNbits instance (bez lomítka na konci)
LNBITS_ADMIN_KEY=tvuj_admin_klic       # Admin API klíč z LNbits → Settings → Users
LNBITS_INVOICE_KEY=tvuj_invoice_klic   # Invoice API klíč z LNbits → Settings → Users
SECRET_KEY=nejaky_dlouhy_nahodny_retez # Libovolný dlouhý řetězec pro JWT tokeny
```

> 💡 **Jak získat API klíče v LNbits:** Přihlaš se do LNbits → vlevo vyber peněženku → záložka **API info** → zkopíruj Admin key a Invoice/read key.

### 3. Spusť aplikaci

```bash
docker compose up -d --build
```

Počkej ~30 sekund než se vše sestaví a spustí.

### 4. Otevři v prohlížeči

- **Dětský pohled:** http://localhost:5173
- **Rodičovský panel:** http://localhost:5173 → klikni na 🔒 ikonu

### 5. První přihlášení

Při prvním spuštění není nastaven žádný PIN. Zavolej setup endpoint:

```bash
curl -X POST http://localhost:8000/api/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"pin":"tvuj_pin"}'
```

**Windows (PowerShell):**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/auth/setup" -Method POST -ContentType "application/json" -Body '{"pin":"12345"}'
```

---

## Aktualizace

Při vydání nové verze:

```bash
git pull origin main
docker compose up -d --build
```

---

## Lokální úpravy konfigurace

Pokud potřebuješ upravit `docker-compose.yml` pro své prostředí (porty, cesty), použij soubor `docker-compose.override.yml` – ten se nepřepisuje při `git pull`:

```yaml
# docker-compose.override.yml
services:
  frontend:
    ports:
      - "8080:80"   # změna portu frontendu
```

---

## Architektura

```
chores-rewards/
├── app/              # Backend – FastAPI (Python)
│   ├── routers/      # API endpointy
│   ├── models.py     # Pydantic modely
│   ├── auth.py       # PIN autentizace, JWT tokeny
│   └── database.py   # SQLite připojení a migrace
├── frontend/         # Frontend – Vue 3
│   └── src/
│       ├── views/    # Stránky (ChildView, ParentView)
│       └── components/
├── sql/              # SQL migrace
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

| Služba | Port | Popis |
|--------|------|-------|
| Frontend (Vue) | 5137 | Webové rozhraní |
| Backend (FastAPI) | 8000 | REST API |

---

## Záloha dat

Všechna data jsou uložena v jednom souboru:

```
data/chores.db
```

Pro zálohu stačí zkopírovat tento soubor:

```powershell
# Windows
Copy-Item .\data\chores.db .\data\chores.db.backup
```

---

## Lightning platby – podporované formáty

| Formát | Příklad | Popis |
|--------|---------|-------|
| Lightning Address | `jmeno@domain.com` | Standardní LN adresa |
| Bitlifi alias | `jmeno@bitlifi.com` | Bitlifi uživatelský alias |
| Bitlifi tel. číslo | `+4207xxxxxx@bitlifi.com` | Bitlifi přes tel. číslo |

---

## Licence

MIT – volně použitelné a upravitelné.
