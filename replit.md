# Overview

This is NBAdex, a Discord bot for collecting and trading NBA-themed collectibles (similar to countryballs but for NBA teams/players). The project is a fork/clone of BallsDex, adapted to use NBA collectibles instead of countryballs. It includes:

- A Discord bot built with discord.py for spawning and managing collectibles
- An admin panel built with Django + Gunicorn (production server) for managing the bot's database and content
- Neon PostgreSQL database for persistent storage
- Support for trading, favoriting, and collecting NBA-themed cards
- Drop command that allows users to spawn collectibles for others to catch
- Admin commands for moderation and bot management
- OAuth2 authentication for the admin panel

# Recent Changes (Session: Nov 23, 2025)

## New Features

### Coins System
- **Player Coins Management**: Each player has a coin balance (stored in `Player.coins`)
- **Coin Commands**:
  - `/nba player coins`: Check your current coin balance
  - `/nba player coins-give <user> <amount>`: Transfer coins to another player
- **All commands are admin-customizable** via Django admin panel
- Location: `ballsdex/packages/balls/cog.py` (lines 1137-1204)

### Packs System
- **Complete pack system** for purchasing and opening collectible packs
- **Pack Models**:
  - `Pack`: Defines pack name, description, cost, and availability
  - `PackReward`: Links packs to balls with weighted drop rates
  - `PlayerPack`: Tracks pack ownership and inventory per player
- **Pack Commands**:
  - `/packs list`: List all available packs with costs
  - `/packs buy <pack_name>`: Purchase a pack using coins
  - `/packs inventory`: View your owned packs
  - `/packs open <pack_name>`: Open a pack and get a random ball
  - `/packs give <user> <pack_name> [quantity]`: Gift packs to other players
- **Location**: `ballsdex/packages/packs/cog.py` (complete module)
- **Admin Customization**: Fully customizable in Django admin panel
  - Create/manage packs (name, description, cost, enabled status)
  - Assign balls to packs with drop rate weights
  - View player pack inventory

### Leaderboard Redesign
- Professional green color scheme (0x1f8b4c)
- Global stats display (top players count, total collected, highest count)
- Clean format: `🥇 Player Name · **Count**`
- Medals for top 3, numbers for ranks 4-10

### 24-Hour Daily Claim System
- `/nba claim`: Claim daily NBA card with 24-hour cooldown per player
- **Silent cooldown**: No message shown when on cooldown
- Shows congratulations message with card details on successful claim
- Tracks claim time in `Player.extra_data['last_claim_date']`

### Drop Command Enhancements
- **Location**: `ballsdex/packages/balls/cog.py` (lines 969-1045)
- Features: Tradeable check, favorite confirmation, locked item handling
- Self-catch detection with custom message: "You caught your own drop? What a cheap thing to do."
- Automatically tracked as "obtained by trade"

## Production Deployment
- Switched from Django development server to **Gunicorn 23.0.0** with 4 workers
- Collected 135 static files for production serving
- Admin Panel: Listens on `0.0.0.0:5000`
- Both workflows (Discord Bot + Admin Panel) running simultaneously

## Configuration Fixes
- Fixed CSRF issues for Replit iframe environment:
  - Enabled session-based CSRF tokens (`CSRF_USE_SESSIONS = True`)
  - Allowed iframe embedding (`X_FRAME_OPTIONS = 'ALLOWALL'`)
  - Configured cookies with `SameSite='Lax'` for development environment
- Fixed database URL SSL parameter from `sslmode` to `ssl` for asyncpg compatibility

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
- `Player`: Discord users who collect cards (includes coins and extra_data for cooldowns)
- `Trade`: Trading system between players
- `Special`: Special event cards (e.g., shiny variants)
- `Pack`: Purchasable packs containing random balls
- `PackReward`: Weighted ball rewards in packs
- `PlayerPack`: Player pack ownership and inventory
- `GuildConfig`: Server-specific settings
- `BlacklistedID/BlacklistedGuild`: Moderation system

### Bot Architecture

**Decision**: Cog-based modular design with separation of concerns

**Rationale**: Discord.py cogs provide clean separation of functionality and hot-reloading capabilities for development.

**Key cogs**:
- `CountryBallsSpawner`: Handles spawning collectibles in channels based on message activity
- `Balls`: Player inventory management, info commands, donations, coins, daily claims, leaderboard
- `Packs`: Pack purchasing, opening, inventory, and gifting system
- `Admin`: Administrative commands for bot owners/staff
- `Config`: Server configuration and setup
- `Trade`: Trading system between players

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