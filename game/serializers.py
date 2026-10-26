from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import Player, CharacterClass, NPC, DialogueOption, Quest, QuestObjective, PlayerQuest


class CharacterClassSerializer(serializers.ModelSerializer):
    """Класс персонажа — для выбора при регистрации"""
    
    class Meta:
        model = CharacterClass
        fields = [
            'id', 'name', 'description', 'icon',
            'base_strength', 'base_agility', 'base_intelligence',
            'base_endurance', 'base_sanity',
        ]


class RegisterSerializer(serializers.ModelSerializer):
    """Регистрация нового игрока"""
    
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        label='Подтверждение пароля',
    )
    email = serializers.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm']
    
    def validate(self, attrs):
        """Проверка, что пароли совпадают"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password': 'Пароли не совпадают'
            })
        return attrs
    
    def validate_username(self, value):
        """Проверка, что ник свободен"""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Этот ник уже занят')
        return value
    
    def validate_email(self, value):
        """Проверка, что email не занят"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Этот email уже используется')
        return value
    
    def create(self, validated_data):
        """Создаём User + Player"""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=password,
        )
        
        # Создаём Player, автоматически привязанный к User
        Player.objects.create(user=user)
        
        return user


class PlayerSerializer(serializers.ModelSerializer):
    """Профиль игрока — для отображения"""
    
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    character_class = CharacterClassSerializer(read_only=True)
    
    class Meta:
        model = Player
        fields = [
            'id', 'username', 'email', 'character_class',
            'level', 'experience', 'experience_to_next',
            'strength', 'agility', 'intelligence', 'endurance', 'sanity',
            'stat_points',
            'health', 'max_health', 'mana', 'max_mana', 'gold',
            'faction', 'is_in_tutorial', 'email_verified',
            'created_at',
            'enemies_killed',
        ]


# ==========================================
# 🧙‍♂️ NPC И ДИАЛОГИ
# ==========================================

class DialogueOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DialogueOption
        fields = ['id', 'text', 'response_text', 'order', 'gives_quest']

class NPCSerializer(serializers.ModelSerializer):
    dialogue_options = DialogueOptionSerializer(many=True, read_only=True)
    
    class Meta:
        model = NPC
        fields = ['id', 'name', 'slug', 'image_path', 'greeting_text', 'post_quest_dialogue', 'dialogue_options']


# ==========================================
# 📜 КВЕСТЫ
# ==========================================

class QuestObjectiveSerializer(serializers.ModelSerializer):
    target_name = serializers.SerializerMethodField()
    
    class Meta:
        model = QuestObjective
        fields = ['id', 'order', 'objective_type', 'target_name', 'required_count']
        
    def get_target_name(self, obj):
        if obj.objective_type == 'kill' and obj.target_enemy:
            return obj.target_enemy.name
        if obj.objective_type == 'collect' and obj.target_item:
            return obj.target_item.name
        return "Неизвестная цель"


class QuestSerializer(serializers.ModelSerializer):
    objectives = QuestObjectiveSerializer(many=True, read_only=True)
    giver_name = serializers.CharField(source='giver_npc.name', read_only=True)
    turn_in_name = serializers.CharField(source='turn_in_npc.name', read_only=True)
    
    # 🆕 Добавляем данные о предметах
    reward_item_name = serializers.CharField(source='reward_item.name', read_only=True)
    reward_item_slug = serializers.CharField(source='reward_item.slug', read_only=True)
    reward_item_rarity = serializers.CharField(source='reward_item.rarity', read_only=True)
    # 🆕 Добавляем путь к картинке предмета
    reward_item_image = serializers.CharField(source='reward_item.image_path', read_only=True)
    
    reward_resource_name = serializers.CharField(source='reward_resource.name', read_only=True)
    reward_resource_slug = serializers.CharField(source='reward_resource.slug', read_only=True)
    reward_resource_rarity = serializers.CharField(source='reward_resource.rarity', read_only=True)
    # 🆕 Добавляем путь к картинке ресурса
    reward_resource_image = serializers.CharField(source='reward_resource.image_path', read_only=True)
    
    class Meta:
        model = Quest
        fields = [
            'id', 'title', 'slug', 'description', 
            'giver_name', 'turn_in_name', 'required_level', 'is_repeatable',
            'reward_exp', 'reward_gold', 
            'reward_item', 'reward_item_qty', 'reward_item_name', 'reward_item_slug', 'reward_item_rarity', 'reward_item_image',
            'reward_resource', 'reward_resource_qty', 'reward_resource_name', 'reward_resource_slug', 'reward_resource_rarity', 'reward_resource_image',
            'reward_vip_days',
            'objectives'
        ]


class PlayerQuestSerializer(serializers.ModelSerializer):
    # 🆕 Вложенный квест теперь отдает полные данные, включая предметы (через QuestSerializer)
    quest_details = QuestSerializer(source='quest', read_only=True)
    
    class Meta:
        model = PlayerQuest
        fields = ['id', 'quest_details', 'status', 'progress_data', 'started_at']


class AllQuestsSerializer(serializers.ModelSerializer):
    giver_name = serializers.SerializerMethodField()
    objectives = QuestObjectiveSerializer(many=True, read_only=True)
    
    # 🆕 ДОБАВЛЯЕМ ПОЛЯ ДЛЯ ПРЕДМЕТОВ
    reward_item_name = serializers.CharField(source='reward_item.name', read_only=True)
    reward_item_slug = serializers.CharField(source='reward_item.slug', read_only=True)
    reward_item_rarity = serializers.CharField(source='reward_item.rarity', read_only=True)
    # 🆕 Путь к картинке предмета
    reward_item_image = serializers.CharField(source='reward_item.image_path', read_only=True)
    
    reward_resource_name = serializers.CharField(source='reward_resource.name', read_only=True)
    reward_resource_slug = serializers.CharField(source='reward_resource.slug', read_only=True)
    reward_resource_rarity = serializers.CharField(source='reward_resource.rarity', read_only=True)
    # 🆕 Путь к картинке ресурса
    reward_resource_image = serializers.CharField(source='reward_resource.image_path', read_only=True)
    
    class Meta:
        model = Quest
        fields = [
            'id', 'title', 'description', 'required_level', 
            'giver_name', 'reward_exp', 'reward_gold', 'objectives',
            # 🆕 ДОБАВЛЯЕМ ИХ В СПИСОК
            'reward_item', 'reward_item_qty', 'reward_item_name', 'reward_item_slug', 'reward_item_rarity', 'reward_item_image',
            'reward_resource', 'reward_resource_qty', 'reward_resource_name', 'reward_resource_slug', 'reward_resource_rarity', 'reward_resource_image',
        ]
        
    def get_giver_name(self, obj):
        if obj.giver_npc:
            return obj.giver_npc.name
        return "Неизвестно"