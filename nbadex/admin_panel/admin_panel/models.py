"""Admin panel models registration"""
from django.contrib import admin
from ballsdex.core.models import Pack, PackReward, PlayerPack
from admin_panel.admin import BallsdexAdminSite


class PackRewardInline(admin.TabularInline):
    """Inline admin for pack rewards"""
    model = PackReward
    extra = 1
    fields = ('ball', 'weight')


@admin.register(Pack, site=BallsdexAdminSite)
class PackAdmin(admin.ModelAdmin):
    """Admin interface for packs"""
    list_display = ('name', 'cost', 'enabled')
    list_filter = ('enabled', 'cost')
    search_fields = ('name',)
    inlines = [PackRewardInline]
    fieldsets = (
        ('Pack Info', {
            'fields': ('name', 'description', 'enabled')
        }),
        ('Cost', {
            'fields': ('cost',)
        }),
    )


@admin.register(PlayerPack, site=BallsdexAdminSite)
class PlayerPackAdmin(admin.ModelAdmin):
    """Admin interface for player packs"""
    list_display = ('player', 'pack', 'quantity', 'created_at')
    list_filter = ('pack', 'created_at')
    search_fields = ('player__discord_id',)
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Ownership', {
            'fields': ('player', 'pack')
        }),
        ('Quantity', {
            'fields': ('quantity',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
