"""Admin panel models registration"""
from django.contrib import admin
from ballsdex.core.models import Pack, PackReward, PlayerPack


class PackRewardInline(admin.TabularInline):
    """Inline admin for pack rewards"""
    model = PackReward
    extra = 1
    fields = ('ball', 'weight')
    raw_id_fields = ('ball',)


class PackAdmin(admin.ModelAdmin):
    """Admin interface for packs"""
    list_display = ('name', 'cost', 'enabled', 'get_reward_count')
    list_filter = ('enabled', 'cost')
    search_fields = ('name', 'description')
    inlines = [PackRewardInline]
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'description', 'cost', 'enabled'),
            'description': 'Configure pack name, cost, and availability'
        }),
    )

    def get_reward_count(self, obj):
        """Display count of balls in pack"""
        return obj.rewards.count()
    get_reward_count.short_description = 'Balls in Pack'


class PlayerPackAdmin(admin.ModelAdmin):
    """Admin interface for player pack inventory"""
    list_display = ('get_player', 'pack', 'quantity', 'created_at')
    list_filter = ('pack', 'created_at')
    search_fields = ('player__discord_id',)
    readonly_fields = ('created_at',)
    raw_id_fields = ('player', 'pack')
    fieldsets = (
        ('Pack Ownership', {
            'fields': ('player', 'pack', 'quantity'),
            'description': 'View and manage player pack inventory'
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def get_player(self, obj):
        """Display player info"""
        return f"{obj.player.discord_id} ({getattr(obj.player, 'name', 'Unknown')})"
    get_player.short_description = 'Player'
