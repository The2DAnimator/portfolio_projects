from django.core.management.base import BaseCommand
from projects.models import Category

class Command(BaseCommand):
    help = 'Seed initial categories'
    
    def handle(self, *args, **options):
        categories = [
            'Digital Art',
            'Photography', 
            'Video Production',
            'Audio Production',
            'Animation',
            'Graphic Design',
            '3D Modeling',
            'Web Design',
        ]
        
        for category_name in categories:
            Category.objects.get_or_create(name=category_name)
        
        self.stdout.write(self.style.SUCCESS('Successfully seeded categories'))
