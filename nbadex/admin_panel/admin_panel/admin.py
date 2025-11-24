from django.contrib import admin

from ballsdex.settings import settings
from bd_models.models import Pack, CoinReward, CoinTransaction


class BallsdexAdminSite(admin.AdminSite):
    site_header = f"{settings.bot_name} administration"
    site_title = f"{settings.bot_name} admin panel"
    site_url = None  # type: ignore
    final_catch_all_view = False


class CoinRewardInline(admin.TabularInline):
    model = CoinReward
    extra = 1


class PackAdmin(admin.ModelAdmin):
    list_display = ("emoji", "name", "cost", "enabled", "updated_at")
    list_filter = ("enabled", "created_at")
    search_fields = ("name",)
    inlines = [CoinRewardInline]
    fieldsets = (
        ("Pack Information", {
            "fields": ("name", "emoji", "cost", "description", "enabled")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    readonly_fields = ("created_at", "updated_at")


class CoinTransactionAdmin(admin.ModelAdmin):
    list_display = ("player", "amount", "reason", "created_at")
    list_filter = ("created_at", "reason")
    search_fields = ("player__discord_id",)
    readonly_fields = ("player", "amount", "reason", "pack", "created_at")
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# Register models
admin.site.register(Pack, PackAdmin)
admin.site.register(CoinTransaction, CoinTransactionAdmin)
