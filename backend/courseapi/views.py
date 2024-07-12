from rest_framework.generics import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import (MemberRoleSerializer,
                          StudentPlainSerializer,
                          HomeworkListSerializer,
                          HomeworkSendSerializer,
                          HomeworkCheckSerializer,
                          MemberSerializer,
                          TaskSerializer,
                          TaskPlainSerializer,
                          StatisticSerializer)
from rest_framework import generics
from django.db.models import Count, F
from django.db import transaction
from django.db.utils import DatabaseError
from django.utils import timezone

from .models import Member, Homework, Task, Statistic
from .utils import updateStatisticCheck
from .task import save_hw_to_gsheets, save_mark_to_gsheets
import environ
import os


env = environ.Env()
environ.Env.read_env()


class TestAPIView(APIView):
    def get(self, request):
        return Response(status=200)


class StudentListPagination(PageNumberPagination):
    page_size = 2
    page_size_query_param = 'page_size'
    max_page_size = 1000


class MemberCreateAPIView(generics.CreateAPIView):
    queryset = Member
    serializer_class = MemberSerializer

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            response = super().create(request, args, kwargs)
            if response.data['role'] == Member.Role.STUDENT:
                try:
                    Statistic(student_id=response.data['id']).save()
                except DatabaseError:
                    return Response({'message': 'ошибка создания статистики'}, status=400)
        return response


class MemberDeleteAPIView(generics.DestroyAPIView):
    queryset = Member
    serializer_class = MemberSerializer
    lookup_field = 'username'


class MemberExpelAPIView(APIView):
    def delete(self, request, username, student_username):
        student = get_object_or_404(Member, username=student_username, tutor__username=username)
        student.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MemberRoleAPIView(generics.RetrieveAPIView):
    queryset = Member.objects.all()
    serializer_class = MemberRoleSerializer
    lookup_field = 'username'


class MemberStudentsAPIView(generics.ListAPIView):
    serializer_class = StudentPlainSerializer

    def get_queryset(self):
        return Member.objects.filter(tutor__username=self.kwargs['username']).all()


class MemberStudentsByTaskAPIView(generics.ListAPIView):
    serializer_class = StudentPlainSerializer

    def get_queryset(self):
        return Member.objects.filter(tutor__username=self.kwargs['username'],
                                     hws__task_id=self.kwargs['task'],
                                     hws__mark__isnull=True).all()


class HomeworkAPIView(generics.ListAPIView):
    serializer_class = HomeworkListSerializer

    def get_queryset(self):
        return Homework.objects.filter(owner__username=self.kwargs['username']).all().order_by('task')


class HomeworkSendAPIView(APIView):
    def post(self, request, username):
        member = get_object_or_404(Member, username=username)
        instance = Homework.objects.filter(owner__username=username, task_id=request.data['task'])
        if instance:
            instance = instance[0]
            serializer = HomeworkSendSerializer(data={
                'owner': instance.owner_id,
                'task': instance.task_id,
                'url': request.data['url']
            },
                instance=instance)
        else:
            serializer = HomeworkSendSerializer(data={
                'owner': member.pk,
                'task': request.data['task'],
                'url': request.data['url']
            })
        serializer.is_valid(raise_exception=True)
        serializer.save()

        try:
            save_hw_to_gsheets.delay(member.gsheets_id, serializer.data['task'], serializer.data['url'])
        except save_hw_to_gsheets.OperationalError as error:
            print(error)

        return Response({
            'task': serializer.data['task'],
            'url': serializer.data['url'],
            'username': member.username
        })


class HomeworkCheckAPIView(APIView):
    def put(self, request, username):
        member = get_object_or_404(Member, username=username)
        instance = get_object_or_404(Homework, owner__username=username, task_id=request.data['task'])
        prev_mark = instance.mark
        serializer = HomeworkCheckSerializer(data={
            'mark': request.data['mark']
        }, instance=instance)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()
            try:
                updateStatisticCheck(username, instance.task_id, prev_mark, serializer.data['mark'])
                try:
                    save_mark_to_gsheets.delay(member.gsheets_id, instance.task_id, serializer.data['mark'])
                except save_hw_to_gsheets.OperationalError as error:
                    print(error)
            except DatabaseError:
                return Response({'message': 'ошибка обновления статистики'}, status=400)

        return Response({
            'task': instance.task_id,
            'mark': serializer.data['mark'],
            'username': member.username
        })


class HomeworkGroupedAPIView(APIView):
    def get(self, request, username):
        unchecked_homeworks = Homework.objects.filter(owner__tutor__username=username, mark__isnull=True)
        grouped_info = unchecked_homeworks.values('task_id').annotate(kol=Count('task_id')).order_by('task_id')
        return Response(grouped_info)


class TaskAPIView(generics.ListAPIView):
    serializer_class = TaskSerializer

    def get_queryset(self):
        return Task.objects.all().order_by('id')


class StatisticAPIView(generics.ListAPIView):
    serializer_class = StatisticSerializer

    def get_queryset(self):
        tutor = self.kwargs.get('username', None)
        if tutor:
            statistics = Statistic.objects.filter(student__tutor__username=tutor)
        else:
            statistics = Statistic.objects
        return (statistics.annotate(username=F('student__username'), average=F('sum') / F('passed'))
                .order_by('-passed', '-average', '-project')
                .all()[:self.kwargs['limit']])


class TaskStartedAPIView(generics.ListAPIView):
    serializer_class = TaskPlainSerializer

    def get_queryset(self):
        return Task.objects.filter(start_date__lte=timezone.now())


class TaskEndedAPIView(generics.ListAPIView):
    serializer_class = TaskPlainSerializer

    def get_queryset(self):
        return Task.objects.filter(end_date__lte=timezone.now())
