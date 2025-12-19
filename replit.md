# Overview

This is NBAdex, a Discord bot for collecting and trading NBA-themed collectibles (similar to countryballs but for NBA teams/players). The project is a fork/clone of BallsDex, adapted to use NBA collectibles instead of countryballs. It includes:

- A Discord bot built with discord.py for spawning and managing collectibles
- An admin panel built with Django + Gunicorn (production server) for managing the bot's database and content
- Neon PostgreSQL database for persistent storage
- Support for trading, favoriting, and collecting NBA-themed cards
- Drop command that allows users to spawn collectibles for others to catch
- Admin commands for moderation and bot management
- OAuth2 authentication for the admin panel

# Recent Changes (Session: Dec 19, 2025)

- **PACKS & COINS ECONOMY SYSTEM FULLY OPERATIONAL**: Complete economy system with coins and pack features
  - **Player coins**: `coins` field on Player model (INTEGER, default 0)
  - **Quicksell values**: `quicksell_value` field on Ball model for selling NBAs
  - **Pack system**: Pack model with name, description, price, cards_count, min/max rarity, special filters, daily limits
  - **Pack inventory**: PlayerPack model for tracking owned packs
  - **Pack history**: PackOpenHistory model for tracking pack opens

  **Discord Commands (9 commands synced):**
  - `/coins balance` - Check your or another user's coin balance
  - `/coins sell` - Quicksell an NBA for coins (1.5x bonus for special cards)
  - `/coins bulk_sell` - Sell multiple NBAs at once with filters
  - `/pack list` - View available packs for purchase
  - `/pack buy` - Purchase a pack with coins
  - `/pack open` - Open a pack from inventory to receive NBAs
  - `/pack inventory` - View your owned packs

  **Admin Commands:**
  - `/admin coins add/remove/set/check` - Manage player coin balances
  - `/admin packs add/remove/check` - Manage player pack inventories

  **Django Admin Panel:**
  - PackAdmin: Manage packs with rarity ranges, special event filters, daily limits
  - PlayerPackAdmin: View/edit player pack inventories
  - PackOpenHistoryAdmin: Read-only history of pack opens
  - BallAdmin updated with Economy section for quicksell_value

  **Database Tables (Neon PostgreSQL):**
  - `pack`: Stores pack definitions
  - `playerpack`: Player pack inventories
  - `packopenhistory`: Pack opening history
  - Columns added: `player.coins`, `ball.quicksell_value`

# Previous Session (Nov 27, 2025)

- **BETTING SYSTEM FULLY OPERATIONAL**: Complete betting system with 7 commands, all database issues resolved
  - Class named `Bet` for correct `/bet` command prefix (not `/betting`)
  - Database tables created: `bet`, `betstake`, `bethistory` (PostgreSQL with proper foreign keys)
  - Tortoise ORM models: `Bet`, `BetStake`, `BetHistory` in `ballsdex.core.models`
  - 7 betting commands working: `/bet begin`, `/bet add`, `/bet remove`, `/bet view`, `/bet cancel`, `/bet bulk add`, `/bet history`
  - Commands restricted to betting channel (1443544409684836382) in admin guild (1440962506796433519)
  - Channel check enforced via `@app_commands.check(betting_channel_check)` on each command
  - `/bet add` and `/bet remove` use `BallInstanceTransform` for autocomplete with NBA filtering
  - `/bet bulk add` supports filtering by ball type, special event, sort order
  - Betting uses in-memory TTLCache (30-min timeout for active bets)
  - Structure mirrors Trade cog exactly for consistency
  - Created new cog: `ballsdex.packages.betting`
  - All commands synced and operational

# Previous Session (Nov 25, 2025)
- **COMPLETE REMOVAL OF COINS SYSTEM**: Dropped `coins` column from database and removed all economy-related code
  - Fixed database integrity constraint violation (NOT NULL on coins field)
  - Removed all `coins=0` workarounds from 18 Player.get_or_create() calls across codebase
  - Bot now creates players without any economy field dependencies
  - This prevents the issue from ever happening again
- Bot running with 27 NBAs loaded and fully operational

## Previous Session (Nov 24, 2025)
- Removed economy system (coins, packs, CoinReward, CoinTransaction) - not needed
- Bot and admin panel running smoothly with all core features

## Previous Session (Nov 23, 2025)
- **Drop Command** (`/nba drop`): Users can drop NBAs from inventory for others to catch
- Switched to Gunicorn 23.0.0 for production deployment
- Fixed CSRF and database SSL configuration for Replit

# User Preferences

Preferred communication style: Simple, everyday language.
Deployment: Production-grade server (Gunicorn), not development server.
Database Management: Clean up unused fields and systems entirely rather than using workarounds.

# System Architecture

## Core Technologies

- **Bot Framework**: discord.py with app_commands (slash commands)
- **Admin Panel**: Django 5.x with custom admin interface
- **Database**: PostgreSQL via Tortoise ORM (bot) and Django ORM (admin panel)
- **Image Generation**: Pillow (PIL) for generating collectible card images
- **Deployment**: Designed for Docker/Replit environments

## Architecture Decisions

### Database Layer

**Decision**: Dual ORM approach - Tortoise ORM for the bot, Django ORM for admin panel

**Rationale**: The bot uses Tortoise ORM for async database operations which are essential for Discord bots. The admin panel uses Django's ORM which provides a mature admin interface out-of-the-box. Both ORMs connect to the same PostgreSQL database.

**Key models**:
- `Ball`: Represents NBA collectibles (teams, players) - includes `quicksell_value` for economy
- `BallInstance`: Individual cards owned by players
- `Player`: Discord users who collect cards - includes `coins` balance
- `Trade`: Trading system between players
- `Bet`: Betting records (player1, player2, winner, started_at, ended_at, cancelled)
- `BetStake`: Individual NBAs staked in a bet (references Bet, Player, BallInstance)
- `BetHistory`: Permanent history of completed/cancelled bets
- `Pack`: Pack definitions with price, rarity ranges, special filters, daily limits
- `PlayerPack`: Player pack inventories (quantity owned per pack type)
- `PackOpenHistory`: History of pack openings with cards received
- `Special`: Special event cards (e.g., shiny variants)
- `GuildConfig`: Server-specific settings
- `BlacklistedID/BlacklistedGuild`: Moderation system

### Bot Architecture

**Decision**: Cog-based modular design with separation of concerns

**Rationale**: Discord.py cogs provide clean separation of functionality and hot-reloading capabilities for development.

**Key cogs**:
- `CountryBallsSpawner`: Handles spawning collectibles in channels based on message activity
- `Balls`: Player inventory management, info commands, donations
- `Admin`: Administrative commands for bot owners/staff (includes coins and packs admin subgroups)
- `Config`: Server configuration and setup
- `Trade`: Trading system between players
- `Bet`: Betting system with 7 commands - `/bet begin|add|remove|view|cancel|bulk add|history`
- `Coins`: Economy system with `/coins balance|sell|bulk_sell` and `/pack list|buy|open|inventory`

### Spawn System

**Decision**: Configurable spawn manager with support for custom algorithms

**Rationale**: Allows flexibility in how collectibles spawn (frequency, conditions) without hardcoding logic. The spawn manager can be swapped via configuration.

**Implementation**: `BaseSpawnManager` provides interface, actual implementation loaded via `settings.spawn_manager` configuration path.

### Admin Panel

**Decision**: Django admin with OAuth2 Discord authentication

**Rationale**: Django admin provides a robust, battle-tested interface for database management. Discord OAuth2 ensures only authorized Discord users can access the panel.

**Security**: 
- Role-based permissions (staff, admin, team member, co-owner, owner)
- CSRF protection
- Security headers middleware
- Designed for localhost by default (production requires additional configuration)

### Image Generation

**Decision**: Dynamic card generation using PIL with template-based system

**Rationale**: Creates unique card images on-the-fly with stats, backgrounds, and special effects rather than storing pre-rendered images.

**Components**:
- Base card templates
- Ball artwork overlays  
- Special backgrounds (shiny, events)
- Regime/Economy overlays (for different card types)
- Dynamic text rendering for stats and names

### Trading System

**Decision**: Two-step trading with approval mechanism

**Rationale**: Prevents scams and mistakes by requiring both parties to explicitly confirm trades.

**Flow**:
1. User initiates trade and selects cards
2. Partner selects their cards
3. Both users must confirm the final trade
4. Trade is recorded in database with full history

### Configuration System

**Decision**: YAML-based configuration with settings validation

**Rationale**: Human-readable configuration files are easier to maintain than environment variables for complex settings. JSON schema validation ensures correctness.

**Key settings**:
- Discord bot token
- Database connection URL
- Admin role IDs
- Spawn configuration
- Feature toggles

## External Dependencies

### Discord Integration

- **discord.py**: Primary library for Discord bot functionality
- **OAuth2**: Discord OAuth2 for admin panel authentication via python-social-auth

### Database

- **PostgreSQL**: Primary database (Neon.tech hosted instance based on connection string)
- **Tortoise ORM**: Async ORM for bot operations
- **Django ORM**: ORM for admin panel
- **asyncpg**: PostgreSQL driver for Tortoise

### Admin Panel

- **Django**: Web framework for admin panel
- **django-admin-action-forms**: Enhanced admin actions
- **django-admin-inline-paginator**: Pagination for inline models
- **social-auth-app-django**: Discord OAuth2 integration

### Monitoring & Metrics

- **Prometheus**: Metrics collection (via prometheus-client)
- **Sentry**: Error tracking (optional, configured via settings)

### Image Processing

- **Pillow**: Image generation and manipulation for collectible cards

### Utilities

- **PyYAML**: Configuration file parsing
- **aiohttp**: Async HTTP client for Discord webhooks
- **Rich**: Enhanced console output and logging

### Development Tools

- **Poetry**: Dependency management
- **Black**: Code formatting
- **Pre-commit**: Git hooks for code quality
