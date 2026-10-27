import pytest
from django.contrib.auth.models import User
from game.models import Player, Enemy, CharacterClass, Combat
from game.combat import start_combat, player_attack

# 🆕 Фикстура: создает игрока и моба для каждого теста (чтобы не писать одно и то же)
@pytest.fixture
def combat_setup(db):
    # Создаем пользователя и игрока
    user = User.objects.create_user(username='test_hero', password='password123')
    warrior_class = CharacterClass.objects.create(name='Воин', base_strength=10)
    
    player = Player.objects.create(
        user=user,
        character_class=warrior_class,
        strength=10,
        health=100,
        max_health=100,
        level=1
    )
    
    # Создаем моба
    enemy = Enemy.objects.create(
        name='Тестовый Гоблин',
        slug='test_goblin',
        health=50,
        defense=0,
        attack=5,
        xp_reward=50,
        gold_reward=20,
        level=1
    )
    
    # Начинаем бой
    combat = start_combat(player, enemy)
    return combat

# ✅ Тест 1: Проверяем, что удар уменьшает HP моба
@pytest.mark.django_db
def test_attack_reduces_enemy_hp(combat_setup):
    initial_hp = combat_setup.enemy_hp
    result = player_attack(combat_setup)
    
    # Проверяем, что HP моба уменьшилось
    assert result['enemy']['hp'] < initial_hp

# ✅ Тест 2: Проверяем, что убийство моба дает награды (и лог правильный)
@pytest.mark.django_db
def test_killing_enemy_gives_rewards(combat_setup):
    # Ставим мобу 1 HP, чтобы убить его с первого удара
    combat_setup.enemy_hp = 1
    combat_setup.save()
    
    result = player_attack(combat_setup)
    
    # Проверяем, что бой выигран
    assert result['status'] == 'won'
    
    # Проверяем, что в логе победы правильные цифры (те самые, что мы фиксили)
    log_message = result['log'][-1]['message']
    assert '+50 XP' in log_message
    assert '+20 золота' in log_message