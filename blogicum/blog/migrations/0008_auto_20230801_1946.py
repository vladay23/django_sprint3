# Generated by Django 3.2.16 on 2023-08-01 16:46

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0007_comment'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='category',
            name='output_order',
        ),
        migrations.RemoveField(
            model_name='post',
            name='output_order',
        ),
    ]
