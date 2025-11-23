from __future__ import annotations

from django.contrib import admin

from ..models import PackReward


@admin.register(PackReward)
class PackRewardAdmin(admin.ModelAdmin):
    list_display = ("pack", "coins", "get_pack_cost")
    search_fields = ("pack__name",)
    search_help_text = "Search by pack name"
    
    fieldsets = (
        (
            "Pack Reward Configuration",
            {
                "fields": ("pack", "coins", "description"),
            },
        ),
    )
    
    @admin.display(description="Pack Cost")
    def get_pack_cost(self, obj):
        return f"{obj.pack.cost} coins"
