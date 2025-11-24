# Overview

This is NBAdex, a Discord bot for collecting and trading NBA-themed collectibles (similar to countryballs but for NBA teams/players). The project is a fork/clone of BallsDex, adapted to use NBA collectibles instead of countryballs. It includes:

- A Discord bot built with discord.py for spawning and managing collectibles
- An admin panel built with Django + Gunicorn (production server) for managing the bot's database and content
- Neon PostgreSQL database for persistent storage
- Support for trading, favoriting, and collecting NBA-themed cards
- Drop command that allows users to spawn collectibles for others to catch
- Admin commands for moderation and bot management
- OAuth2 authentication for the admin panel

# Recent Changes (Session: Nov 24, 2025)

## Economy System Implementation ✅ COMPLETE
- **Database Models** (Tortoise ORM + Django):
  - `Pack`: Purchasable packs with cost, description, enabled status
  - `CoinReward`: Rewards tied to packs with amount and probability
  - `CoinTransaction`: Complete audit log of all coin movements (player, amount, reason, timestamp)
  - `Player.coins`: Coin balance for each player
  - `PlayerPack`: Tracks pack ownership for each player
- **Discord Commands - Coins** (EconomyCommands cog):
  - ✅ `/coins balance` - Check your coin balance
  - ✅ `/coins leaderboard` - View top 10 coin holders
- **Discord Commands - Trade Coins** (Trade cog):
  - ✅ `/trade coins add` - Add coins to trade proposal (with validation)
  - ✅ `/trade coins remove` - Remove coins from trade proposal
- **Discord Commands - NBA Trading** (Trade cog):
  - ✅ `/trade nba add` - Add NBA collectibles to ongoing trade
  - ✅ `/trade nba remove` - Remove NBA collectibles from ongoing trade
  - ✅ `/trade begin` - Start a trade with another player
  - ✅ `/trade cancel` - Cancel ongoing trade
  - ✅ `/trade view` - View trade proposals
  - ✅ `/trade history` - View trade history with filters
  - ✅ `/trade bulk add` - Bulk add collectibles with filters
- **Discord Commands - Packs** (PacksCommands cog with autocomplete):
  - ✅ `/packs list [sorting] [reverse]` - List packs with optional sort by name/cost and reverse order
  - ✅ `/packs buy pack: [amount]` - Buy packs (autocomplete selection, optional quantity)
  - ✅ `/packs inventory` - View your owned packs
  - ✅ `/packs give user: pack: [amount]` - Give pack to another player (autocomplete, optional quantity)
  - ✅ `/packs open pack: [ephemeral]` - Open a pack from inventory (autocomplete, optional visibility)
- **Admin Panel Integration** ✅ Mostly Working:
  - Pack management: Create/edit packs with full control
  - CoinReward management: Add/edit reward types
  - CoinTransaction history view (read-only, admin-only)
  - All models properly synced between Tortoise ORM (bot) and Django ORM (admin)
- **Economy Features**:
  - Player coins start at 0 (configured via admin panel)
  - All transactions recorded in database for auditing
  - Autocomplete-based pack selection (not pagination)
  - Coin validation: Can't add coins you don't have to trades
  - Coins display in live trade messages with NBAs
  - Coin economy fully controllable through admin panel (no hardcoded values)
  - 10+ commands synced and operational
  - Trade system fully integrated with coins and collectibles
  - Database migrations completed (Pack, CoinReward, CoinTransaction models)
  - Admin panel fully functional with no database errors

## Previous Session (Nov 23, 2025)
- **Drop Command** (`/nba drop`): Users can drop NBAs from inventory for others to catch
- Switched to Gunicorn 23.0.0 for production deployment
- Fixed CSRF and database SSL configuration for Replit

# User Preferences

Preferred communication style: Simple, everyday language.
Deployment: Production-grade server (Gunicorn), not development server.

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
- `Ball`: Represents NBA collectibles (teams, players)
- `BallInstance`: Individual cards owned by players
- `Player`: Discord users who collect cards
- `Trade`: Trading system between players
- `Special`: Special event cards (e.g., shiny variants)
- `GuildConfig`: Server-specific settings
- `BlacklistedID/BlacklistedGuild`: Moderation system

### Bot Architecture

**Decision**: Cog-based modular design with separation of concerns

**Rationale**: Discord.py cogs provide clean separation of functionality and hot-reloading capabilities for development.

**Key cogs**:
- `CountryBallsSpawner`: Handles spawning collectibles in channels based on message activity
- `Balls`: Player inventory management, info commands, donations
- `EconomyCommands`: Coin balance and leaderboard commands
- `PacksCommands`: Pack shop with autocomplete-based selection
- `Admin`: Administrative commands for bot owners/staff
- `Config`: Server configuration and setup
- `Trade`: Trading system between players, coin transfers

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