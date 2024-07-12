from rest_framework import serializers
from .models import Member, Homework, Task, Statistic


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = '__all__'


class MemberRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ('role',)


class StudentPlainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ('username',)


class HomeworkListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Homework
        fields = ('task', 'url', 'mark')


class HomeworkSendSerializer(serializers.ModelSerializer):
    class Meta:
        model = Homework
        fields = ('owner', 'task', 'url')


class HomeworkCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Homework
        fields = ('mark',)


class HomeworkGroupedSerializer(serializers.Serializer):
    task_id = serializers.IntegerField()
    kol = serializers.IntegerField()


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = '__all__'


class TaskPlainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ('id',)


class StatisticSerializer(serializers.ModelSerializer):
    username = serializers.SlugField()
    average = serializers.FloatField()

    class Meta:
        model = Statistic
        exclude = ('id', 'sum')
