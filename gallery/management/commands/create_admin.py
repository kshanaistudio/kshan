from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    def handle(self, *args, **options):
        if not User.objects.filter(username='thepranit').exists():
            User.objects.create_superuser('thepranit', 'admin@example.com', 'Debug@45')
            self.stdout.write(self.style.SUCCESS('Admin user created successfully'))
