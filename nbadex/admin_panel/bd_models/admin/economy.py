from __future__ import annotations

from django.contrib import admin

from ..models import Pack, CoinReward, CoinTransaction, PackContent, EconomyConfig


class PackContentInline(admin.TabularInline):
    model = PackContent
    extra = 1
    fields = ("ball_id", "rarity")


@admin.register(Pack)
class PackAdmin(admin.ModelAdmin):
    list_display = ("emoji", "name", "cost", "enabled")
    list_filter = ("enabled",)
    search_fields = ("name",)
    inlines = [PackContentInline]
    fieldsets = (
        ("Pack Information", {
            "fields": ("name", "emoji", "cost", "description", "enabled")
        }),
    )


@admin.register(CoinReward)
class CoinRewardAdmin(admin.ModelAdmin):
    list_display = ("name", "base_coins")
    search_fields = ("name",)
    fieldsets = (
        ("Reward Information", {
            "fields": ("name", "base_coins", "description")
        }),
    )


@admin.register(CoinTransaction)
class CoinTransactionAdmin(admin.ModelAdmin):
    list_display = ("player", "amount", "reason", "timestamp")
    list_filter = ("timestamp", "reason")
    search_fields = ("player__discord_id", "reason")
    readonly_fields = ("player", "amount", "reason", "timestamp")
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(EconomyConfig)
class EconomyConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "starting_coins", "catch_reward", "pack_open_reward")
    fieldsets = (
        ("Configuration", {
            "fields": ("name",)
        }),
        ("Coin Rewards", {
            "fields": ("starting_coins", "catch_reward", "pack_open_reward"),
            "description": "All values are in coins. Configure your economy rewards here."
        }),
        ("Trading", {
            "fields": ("trade_fee_percent",),
            "description": "Fee as percentage (0.0 to 1.0, e.g., 0.1 = 10%)"
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PackContent)
class PackContentAdmin(admin.ModelAdmin):
    list_display = ("pack", "ball_id", "rarity")
    list_filter = ("pack",)
    search_fields = ("pack__name", "ball_id")
    fieldsets = (
        ("Pack Content", {
            "fields": ("pack", "ball_id", "rarity")
        }),
    )
