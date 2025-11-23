from __future__ import annotations

from datetime import timedelta
from typing import Iterable, cast

from django.contrib import admin
from django.core.cache import cache
from django.db import models
from django.utils.safestring import SafeText, mark_safe
from django.utils.timezone import now

from ballsdex.settings import settings


def transform_media(path: str) -> str:
    return path.replace("/static/uploads/", "").replace(
        "/ballsdex/core/image_generator/src/", "default/"
    )


def image_display(image_link: str) -> SafeText:
    return mark_safe(f'<img src="/media/{transform_media(image_link)}" width="80%" />')


class GuildConfig(models.Model):
    guild_id = models.BigIntegerField(unique=True, help_text="Discord guild ID")
    spawn_channel = models.BigIntegerField(
        blank=True, null=True, help_text="Discord channel ID where balls will spawn"
    )
    enabled = models.BooleanField(
        help_text="Whether the bot will spawn countryballs in this guild"
    )
    silent = models.BooleanField()

    def __str__(self) -> str:
        return str(self.guild_id)

    class Meta:
        managed = True
        db_table = "guildconfig"


class DonationPolicy(models.IntegerChoices):
    ALWAYS_ACCEPT = 1
    REQUEST_APPROVAL = 2
    ALWAYS_DENY = 3
    FRIENDS_ONLY = 4


class PrivacyPolicy(models.IntegerChoices):
    ALLOW = 1
    DENY = 2
    SAME_SERVER = 3
    FRIENDS = 4


class MentionPolicy(models.IntegerChoices):
    ALLOW = 1
    DENY = 2


class FriendPolicy(models.IntegerChoices):
    ALLOW = 1
    DENY = 2


class TradeCooldownPolicy(models.IntegerChoices):
    COOLDOWN = 1
    BYPASS = 2


class Player(models.Model):
    discord_id = models.BigIntegerField(unique=True, help_text="Discord user ID")
    donation_policy = models.SmallIntegerField(
        choices=DonationPolicy.choices, help_text="How you want to handle donations"
    )
    privacy_policy = models.SmallIntegerField(
        choices=PrivacyPolicy.choices, help_text="How you want to handle inventory privacy"
    )
    mention_policy = models.SmallIntegerField(
        choices=MentionPolicy.choices, help_text="Control the bot's mentions"
    )
    friend_policy = models.SmallIntegerField(
        choices=FriendPolicy.choices, help_text="Open or close your friend requests"
    )
    trade_cooldown_policy = models.SmallIntegerField(
        choices=TradeCooldownPolicy.choices, help_text="To bypass or not the trade cooldown"
    )
    extra_data = models.JSONField(blank=True, default=dict)
    coins = models.BigIntegerField(default=0, help_text="Player's coin balance")

    def is_blacklisted(self) -> bool:
        blacklist = cast(
            list[int],
            cache.get_or_set(
                "blacklist",
                BlacklistedID.objects.all().values_list("discord_id", flat=True),
                timeout=300,
            ),
        )
        return self.discord_id in blacklist

    def __str__(self) -> str:
        return (
            f"{'\N{NO MOBILE PHONES} ' if self.is_blacklisted() else ''}#"
            f"{self.pk} ({self.discord_id})"
        )

    class Meta:
        managed = True
        db_table = "player"


class Economy(models.Model):
    name = models.CharField(max_length=64)
    icon = models.ImageField(max_length=200, help_text="512x512 PNG image")

    def __str__(self) -> str:
        return self.name

    class Meta:
        managed = True
        db_table = "economy"
        verbose_name_plural = "economies"


class Regime(models.Model):
    name = models.CharField(max_length=64)
    icon = models.ImageField(max_length=200)

    def __str__(self) -> str:
        return self.name

    class Meta:
        managed = True
        db_table = "regime"


class Special(models.Model):
    name = models.CharField(max_length=64)
    id = models.BigAutoField(primary_key=True, help_text="Use the same ID as the special event")

    def __str__(self) -> str:
        return self.name

    class Meta:
        managed = True
        db_table = "special"


class Ball(models.Model):
    name = models.CharField(max_length=64, help_text="NBA collectible name (e.g., LeBron James)")
    economy = models.ForeignKey(Economy, on_delete=models.PROTECT)
    regime = models.ForeignKey(Regime, on_delete=models.PROTECT)
    rarity = models.FloatField(help_text="How rare is this NBA (0-1, where 1 is most common)")
    emoji = models.CharField(max_length=2)
    catch_names = models.CharField(
        max_length=200,
        blank=True,
        help_text="Catch names separated by semicolons (e.g., 'lebron; bron; king james')",
    )
    description = models.TextField(blank=True, help_text="NBA description")
    image_url = models.CharField(
        max_length=300,
        blank=True,
        help_text="URL to the NBA's image",
    )
    atk = models.IntegerField(default=0)
    hp = models.IntegerField(default=0)
    catch_phrase = models.CharField(max_length=100, blank=True)
    enabled = models.BooleanField(default=True)
    catch_value = models.IntegerField(default=10, help_text="Coins awarded when this NBA is caught")

    def __str__(self) -> str:
        return f"{self.name} ({self.emoji})"

    class Meta:
        managed = True
        db_table = "ball"
        verbose_name = "NBA"
        verbose_name_plural = "NBAs"


class BallInstance(models.Model):
    id = models.BigAutoField(primary_key=True)
    ball = models.ForeignKey(Ball, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    server_id = models.BigIntegerField(help_text="Guild ID where the NBA was caught")
    catch_date = models.DateTimeField(auto_now_add=True)
    shiny = models.BooleanField(default=False, help_text="Is this a shiny variant?")
    special = models.ForeignKey(Special, on_delete=models.SET_NULL, null=True, blank=True)
    obtained_by_trade = models.BooleanField(default=False, help_text="Was this NBA obtained by trade?")

    @admin.display(description="Description")
    def description(self) -> str:
        return f"#{self.id} {self.ball.emoji}"

    @admin.display(description="Catch Time")
    def catch_time(self) -> str:
        return format_dt(self.catch_date, "R") if self.catch_date else "Unknown"

    def __str__(self) -> str:
        return f"#{self.id} - {self.ball.name} {self.ball.emoji}"

    class Meta:
        managed = True
        db_table = "ballinstance"
        verbose_name = "NBA Card"
        verbose_name_plural = "NBA Cards"


class Trade(models.Model):
    id = models.BigAutoField(primary_key=True)
    player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="trades_initiated")
    player2 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="trades_received")
    accepted = models.BooleanField(default=False)
    datetime = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Trade #{self.id} - Player {self.player1.discord_id} <-> Player {self.player2.discord_id}"

    class Meta:
        managed = True
        db_table = "trade"


class TradeObject(models.Model):
    id = models.BigAutoField(primary_key=True)
    trade = models.ForeignKey(Trade, on_delete=models.CASCADE)
    ballinstance = models.ForeignKey(BallInstance, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)

    class Meta:
        managed = True
        db_table = "tradeobject"


class BlacklistedID(models.Model):
    discord_id = models.BigIntegerField(unique=True, help_text="Discord user ID")
    reason = models.CharField(max_length=256)
    moderator_id = models.BigIntegerField(blank=True, null=True)

    def __str__(self) -> str:
        return f"ID: {self.discord_id} - {self.reason[:50]}"

    class Meta:
        managed = True
        db_table = "blacklistedid"


class BlacklistedGuild(models.Model):
    discord_id = models.BigIntegerField(unique=True, help_text="Discord guild ID")
    reason = models.CharField(max_length=256)
    moderator_id = models.BigIntegerField(blank=True, null=True)

    def __str__(self) -> str:
        return f"Guild ID: {self.discord_id} - {self.reason[:50]}"

    class Meta:
        managed = True
        db_table = "blacklistedguild"


class BlacklistHistory(models.Model):
    discord_id = models.BigIntegerField(help_text="Discord user ID")
    reason = models.CharField(max_length=256)
    moderator_id = models.BigIntegerField(blank=True, null=True)
    action_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "blacklisthistory"
        verbose_name_plural = "Blacklist histories"


class Friendship(models.Model):
    since = models.DateTimeField(auto_now_add=True, editable=False)
    player1 = models.ForeignKey(Player, on_delete=models.CASCADE)
    player1_id: int
    player2 = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="friendship_player2_set"
    )
    player2_id: int

    class Meta:
        managed = True
        db_table = "friendship"


class Block(models.Model):
    date = models.DateTimeField(auto_now_add=True, editable=False)
    player1 = models.ForeignKey(Player, on_delete=models.CASCADE)
    player1_id: int
    player2 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="block_player2_set")
    player2_id: int

    class Meta:
        managed = True
        db_table = "block"


class Pack(models.Model):
    name = models.CharField(max_length=64, unique=True, help_text="Pack name (e.g., Common, Rare)")
    cost = models.IntegerField(help_text="Coin cost to buy this pack")
    description = models.TextField(help_text="Pack description for /packs info command")
    enabled = models.BooleanField(default=True, help_text="Whether this pack can be purchased")

    def __str__(self) -> str:
        return f"{self.name} ({self.cost} coins)"

    class Meta:
        managed = True
        db_table = "pack"


class PackReward(models.Model):
    pack = models.OneToOneField(Pack, on_delete=models.CASCADE, related_name="reward")
    coins = models.IntegerField(default=0, help_text="Coins given when pack is opened")
    description = models.TextField(help_text="What this pack gives (for reference)")

    def __str__(self) -> str:
        return f"{self.pack.name} Reward: {self.coins} coins"

    class Meta:
        managed = True
        db_table = "packreward"


class CoinReward(models.Model):
    name = models.CharField(max_length=64, unique=True, help_text="Config name (e.g., 'catch_reward')")
    base_coins = models.IntegerField(default=10, help_text="Base coins awarded for catching an NBA")
    description = models.TextField(help_text="Description of this coin reward configuration")

    def __str__(self) -> str:
        return f"{self.name}: {self.base_coins} coins"

    class Meta:
        managed = True
        db_table = "coinreward"
        verbose_name = "Coin Reward Settings"
        verbose_name_plural = "Coin Reward Settings"


class CoinTransaction(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="transactions")
    amount = models.BigIntegerField(help_text="Coin amount (positive for gain, negative for loss)")
    reason = models.CharField(max_length=128, help_text="Why coins were gained/lost (e.g., 'Pack Purchase')")
    timestamp = models.DateTimeField(auto_now_add=True, editable=False)

    def __str__(self) -> str:
        return f"{self.player}: {self.amount:+d} coins ({self.reason})"

    class Meta:
        managed = True
        db_table = "cointransaction"
        indexes = [models.Index(fields=("player",))]
