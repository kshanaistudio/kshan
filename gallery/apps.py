from django.apps import AppConfig
from django.db.models.signals import post_migrate

def create_default_trial_user(sender, **kwargs):
    try:
        from django.contrib.auth.models import User
        from .models import PhotographerProfile
        
        # Trial user: username: p, password: p
        user, created = User.objects.get_or_create(username='p')
        if created or not user.has_usable_password() or not user.check_password('p'):
            user.set_password('p')
            user.is_staff = True
            user.is_superuser = True
            user.save()
            
        profile, _ = PhotographerProfile.objects.get_or_create(
            user=user,
            defaults={
                'studio_name': 'Trial Studio (P)',
                'display_name': 'Pranit Studio',
                'phone': '+919970343404',
                'city': 'Mumbai',
                'event_credits': 99
            }
        )
    except Exception:
        pass

class GalleryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gallery'

    def ready(self):
        post_migrate.connect(create_default_trial_user, sender=self)
