from __future__ import annotations

from django.contrib import admin

from ..models import CoinReward


@admin.register(CoinReward)
class CoinRewardAdmin(admin.ModelAdmin):
    list_display = ("name", "base_coins", "description")
    search_fields = ("name",)
    search_help_text = "Search by config name"
    
    fieldsets = (
        (
            "Coin Reward Settings",
            {
                "fields": ("name", "base_coins", "description"),
                "description": "Configure coin rewards given to players. Create a 'catch_reward' config to set coins for catching NBAs.",
            },
        ),
    )
