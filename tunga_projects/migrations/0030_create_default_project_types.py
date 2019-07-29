from django.db import migrations
from tunga_utils.constants import PROJECT_TYPE_CHOICES

def create_default_project_types(apps, schema_editor):
    ProjectType = apps.get_model('tunga_projects', 'ProjectType')
    for key, value in PROJECT_TYPE_CHOICES:
        ProjectType.objects.get_or_create(name=value)



class Migration(migrations.Migration):

    dependencies = [
        ('tunga_projects', '0029_projecttype'),
    ]

    operations = [
        migrations.RunPython(create_default_project_types),
    ]