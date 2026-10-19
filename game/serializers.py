from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import Player, CharacterClass


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
            'health', 'max_health', 'mana', 'max_mana', 'gold',
            'faction', 'is_in_tutorial', 'email_verified',
            'created_at',
            'enemies_killed',
        ]