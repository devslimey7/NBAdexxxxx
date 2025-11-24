from django.contrib import admin

from ballsdex.settings import settings
from bd_models.models import Pack, PlayerPack


class BallsdexAdminSite(admin.AdminSite):
    site_header = f"{settings.bot_name} administration"
    site_title = f"{settings.bot_name} admin panel"
    site_url = None  # type: ignore
    final_catch_all_view = False


class PackAdmin(admin.ModelAdmin):
    list_display = ("emoji", "name", "price", "created_at")
    search_fields = ("name",)
    readonly_fields = ("created_at",)
    list_filter = ("created_at",)


class PlayerPackInline(admin.TabularInline):
    model = PlayerPack
    extra = 0
    fields = ("pack", "count")


# Register models
admin.site.register(Pack, PackAdmin)
admin.site.register(PlayerPack)
