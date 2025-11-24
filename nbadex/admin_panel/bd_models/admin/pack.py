from django.contrib import admin

from bd_models.models import Pack, PlayerPack


class PlayerPackInline(admin.TabularInline):
    model = PlayerPack
    extra = 0
    fields = ("pack", "count")


class PackAdmin(admin.ModelAdmin):
    list_display = ("emoji", "name", "cost", "enabled")
    search_fields = ("name",)
    list_filter = ("enabled",)
    fieldsets = (
        ("Pack Info", {"fields": ("name", "description", "emoji")}),
        ("Economy", {"fields": ("cost", "open_reward")}),
        ("Status", {"fields": ("enabled",)}),
    )


class PlayerPackAdmin(admin.ModelAdmin):
    list_display = ("player", "pack", "count")
    search_fields = ("player__discord_id", "pack__name")
    list_filter = ("pack",)


admin.site.register(Pack, PackAdmin)
admin.site.register(PlayerPack, PlayerPackAdmin)
