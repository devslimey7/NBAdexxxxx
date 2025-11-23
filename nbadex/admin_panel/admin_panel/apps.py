from django.contrib.admin.apps import AdminConfig


class BallsdexAdminConfig(AdminConfig):
    default_site = "admin_panel.admin.BallsdexAdminSite"

    def ready(self):
        super().ready()
        # Register pack models with admin site
        try:
            from django.contrib import admin
            from ballsdex.core.models import Pack, PlayerPack
            from . import models
            
            admin.site.register(Pack, models.PackAdmin)
            admin.site.register(PlayerPack, models.PlayerPackAdmin)
        except Exception:
            pass
