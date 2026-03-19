from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_add_enterprise_constraints"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="rid7",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=20,
                null=True,
                unique=True,
                verbose_name="RIDET",
            ),
        ),
    ]
