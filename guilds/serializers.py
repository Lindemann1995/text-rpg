from rest_framework import serializers

from .models import (Guild, GuildMember, GuildApplication, GuildLog, GuildChatMessage, GuildBankItem, GuildBankLog,
)


class GuildMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='player.user.username', read_only=True)
    level = serializers.IntegerField(source='player.level', read_only=True)
    rank_color = serializers.CharField(read_only=True)
    rank_display = serializers.CharField(source='get_rank_display', read_only=True)
    
    # 🆕 ДОБАВЛЯЕМ ЭТО ПОЛЕ
    player_id = serializers.IntegerField(source='player.id', read_only=True)

    class Meta:
        model = GuildMember
        fields = ['id', 'player_id', 'username', 'level', 'rank', 'rank_display', 'rank_color',
                  'joined_at', 'contributed_gold']


class GuildSerializer(serializers.ModelSerializer):
    leader_username = serializers.CharField(source='leader.user.username', read_only=True)
    members_count = serializers.SerializerMethodField()

    class Meta:
        model = Guild
        fields = ['id', 'name', 'tag', 'leader_username', 'treasury_gold',
                  'level', 'is_open', 'banner_preset', 'created_at', 'members_count']

    def get_members_count(self, obj):
        return obj.members.count()


class GuildApplicationSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='player.user.username', read_only=True)
    level = serializers.IntegerField(source='player.level', read_only=True)

    class Meta:
        model = GuildApplication
        fields = ['id', 'username', 'level', 'status', 'created_at']


class GuildLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.user.username', read_only=True, default=None)

    class Meta:
        model = GuildLog
        fields = ['id', 'actor_username', 'action', 'details', 'created_at']


class GuildChatMessageSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='player.user.username', read_only=True)
    rank_color = serializers.SerializerMethodField()
    tag = serializers.CharField(source='guild.tag', read_only=True)

    class Meta:
        model = GuildChatMessage
        fields = ['id', 'username', 'message', 'created_at', 'rank_color', 'tag']

    def get_rank_color(self, obj):
        # Ищем участника в гильдии, чтобы взять его ранг и цвет
        member = obj.guild.members.filter(player=obj.player).first()
        return member.rank_color if member else '#FFFFFF'

from .models import GuildBankItem, GuildBankLog

class GuildBankItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_slug = serializers.CharField(source='item.slug', read_only=True)
    item_image = serializers.CharField(source='item.image_path', read_only=True)

    class Meta:
        model = GuildBankItem
        fields = ['id', 'item_name', 'item_slug', 'item_image', 'quantity']

class GuildBankLogSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.user.username', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = GuildBankLog
        fields = ['id', 'player_name', 'item_name', 'quantity', 'action', 'created_at']