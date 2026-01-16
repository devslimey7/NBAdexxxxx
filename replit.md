# Overview

NBAdex is a Discord bot designed for collecting and trading NBA-themed digital collectibles, similar to how Countryballs are collected and traded. The project aims to provide an engaging platform for NBA fans to interact, collect unique cards, and participate in an in-game economy. It includes a Discord bot for core interactions and an administrative panel for content and user management.

The vision for NBAdex is to become the leading platform for digital NBA collectible trading within the Discord ecosystem, fostering a vibrant community and offering a unique blend of fandom and gaming.

# User Preferences

Preferred communication style: Simple, everyday language.
Deployment: Production-grade server (Gunicorn), not development server.
Database Management: Clean up unused fields and systems entirely rather than using workarounds.

# System Architecture

## Core Technologies

- **Bot Framework**: discord.py with app_commands (slash commands)
- **Admin Panel**: Django 5.x with custom admin interface
- **Database**: Local PostgreSQL 17 (migrated from Neon on Jan 16, 2026) accessed via Tortoise ORM (bot) and Django ORM (admin panel)
  - Data directory: `/home/runner/postgres_data`
  - Socket directory: `/home/runner/postgres_socket`  
  - Connection URL: `postgres://runner:@localhost:5432/nbadex`
  - Daily backup script: `scripts/daily_backup.sh` (keeps 7 days in `/home/runner/backups`)
- **Image Generation**: Pillow (PIL) for generating collectible card images
- **Deployment**: Optimized for Docker/Replit environments

## Architecture Decisions

### Database Layer

A dual ORM approach is employed, using Tortoise ORM for asynchronous bot operations and Django ORM for the admin panel, both connecting to a PostgreSQL database. Key models include `Ball` (collectibles), `BallInstance` (owned cards), `Player` (users with `coins`), `Trade`, `Bet` (and related `BetStake`, `BetHistory`), `Pack` (definitions), `PlayerPack` (inventories), `PackOpenHistory`, `Special`, `GuildConfig`, and moderation-related `BlacklistedID`/`BlacklistedGuild`.

### Bot Architecture

The bot uses a modular, cog-based design for clear separation of concerns and maintainability. Key cogs include `CountryBallsSpawner` (for spawning collectibles), `Balls` (inventory, info), `Admin` (bot management, economy tools), `Config`, `Trade` (trading system), `Bet` (betting system), and `Coins` (economy with pack management).

### Spawn System

A configurable spawn manager (`BaseSpawnManager`) allows for flexible and customizable collectible spawning algorithms, loaded via settings.

### Admin Panel

The admin panel is built with Django Admin, secured with Discord OAuth2 for authentication and role-based permissions. It features CSRF protection and security headers.

### Image Generation

Collectible card images are dynamically generated using Pillow, leveraging base templates, artwork overlays, special backgrounds, and dynamic text rendering for stats and names.

### Trading System

A two-step trading system with an explicit approval mechanism for both parties ensures secure and mistake-free transactions.

### Configuration System

YAML-based configuration with JSON schema validation provides human-readable and robust management of bot settings, including tokens, database URLs, admin roles, and feature toggles.

# External Dependencies

### Discord Integration

- **discord.py**: Core library for Discord bot functionality.
- **OAuth2**: Discord OAuth2 for admin panel authentication via `python-social-auth`.

### Database

- **PostgreSQL**: Primary database.
- **Tortoise ORM**: Asynchronous ORM for bot operations.
- **Django ORM**: ORM for admin panel.
- **asyncpg**: PostgreSQL driver.

### Admin Panel

- **Django**: Web framework for the admin panel.
- **django-admin-action-forms**: Enhancements for admin actions.
- **django-admin-inline-paginator**: Pagination for inline models.
- **social-auth-app-django**: Discord OAuth2 integration.

### Image Processing

- **Pillow**: Used for dynamic generation and manipulation of collectible card images.

### Utilities

- **PyYAML**: For parsing configuration files.
- **aiohttp**: Asynchronous HTTP client.
- **Rich**: Enhanced console output and logging.