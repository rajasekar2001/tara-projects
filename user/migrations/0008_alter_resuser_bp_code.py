# Generated by Django 5.1.7 on 2025-03-20 09:04

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('BusinessPartner', '0007_rename_name_businesspartner_full_name_and_more'),
        ('user', '0007_resuser_bp_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resuser',
            name='bp_code',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='BusinessPartner.businesspartner'),
        ),
    ]
