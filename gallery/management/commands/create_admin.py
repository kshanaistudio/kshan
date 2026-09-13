import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Create initial superuser from environment variables if not already present'

    def handle(self, *args, **options):
        admin_username = os.getenv('DJANGO_SUPERUSER_USERNAME')
        admin_email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@kshan.local')
        admin_password = os.getenv('DJANGO_SUPERUSER_PASSWORD')

        if not admin_username or not admin_password:
            self.stdout.write(self.style.WARNING(
                'Skipping superuser creation: DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD are not set in environment.'
            ))
            return

        if not User.objects.filter(username=admin_username).exists():
            User.objects.create_superuser(admin_username, admin_email, admin_password)
            self.stdout.write(self.style.SUCCESS(f'Superuser "{admin_username}" created successfully.'))
        else:
            self.stdout.write(self.style.NOTICE(f'Superuser "{admin_username}" already exists.'))
