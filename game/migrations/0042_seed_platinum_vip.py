from django.db import migrations


def seed_platinum(apps, schema_editor):
    VipStatus = apps.get_model('game', 'VipStatus')
    VipBonus = apps.get_model('game', 'VipBonus')
    VipItemTemplate = apps.get_model('game', 'VipItemTemplate')

    status, _ = VipStatus.objects.get_or_create(
        slug='platinum',
        defaults={
            'name': 'Тень Платинум',
            'color_hex': '#B9A7FF',
            'description': 'Элитный статус. Ускоренная прокачка и повышенный доход.',
            'is_active': True,
        },
    )

    bonuses = [
        ('experience_multiplier', 2.0, 'Опыт x2'),
        ('gold_multiplier', 1.5, 'Золото x1.5'),
        ('chat_color', 1.0, 'Платиновый цвет в чате'),
    ]
    for btype, value, desc in bonuses:
        VipBonus.objects.get_or_create(
            vip_status=status, bonus_type=btype,
            defaults={'value': value, 'description': desc, 'is_active': True},
        )

    templates = [
        (1, 'Тень Платинум (1 день)', 'platinum_1d', 'vip/platinum_1d.png'),
        (7, 'Тень Платинум (7 дней)', 'platinum_7d', 'vip/platinum_7d.png'),
        (30, 'Тень Платинум (30 дней)', 'platinum_30d', 'vip/platinum_30d.png'),
    ]
    for days, name, slug, image in templates:
        VipItemTemplate.objects.get_or_create(
            slug=slug,
            defaults={
                'vip_status': status,
                'days': days,
                'name': name,
                'image_path': image,
                'rarity': 'legendary',
                'is_active': True,
            },
        )


def unseed_platinum(apps, schema_editor):
    VipStatus = apps.get_model('game', 'VipStatus')
    VipStatus.objects.filter(slug='platinum').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('game', '0041_vipitemtemplate_vipstatus_rewardentry_and_more'),
    ]
    operations = [
        migrations.RunPython(seed_platinum, unseed_platinum),
    ]