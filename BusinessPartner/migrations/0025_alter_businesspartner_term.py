# Generated by Django 5.1.5 on 2025-04-07 12:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('BusinessPartner', '0024_alter_businesspartner_business_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='businesspartner',
            name='term',
            field=models.CharField(choices=[('T1-Credit 30 Days', 'T1'), ('T2-Credit 45 Days', 'T2'), ('T3-Credit 60 Days', 'T3'), ('CH-Cash Customer', 'CH')], max_length=100),
        ),
    ]
