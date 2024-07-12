"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from courseapi import views

urlpatterns = [
    path('api/v1/test', views.TestAPIView.as_view()),
    path('api/v1/newmember', views.MemberCreateAPIView.as_view()),
    path('api/v1/delmember/<slug:username>', views.MemberDeleteAPIView.as_view()),

    path('api/v1/statistic/<int:limit>', views.StatisticAPIView.as_view()),

    path('api/v1/timetable', views.TaskAPIView.as_view()),
    path('api/v1/tasks/started', views.TaskStartedAPIView.as_view()),
    path('api/v1/tasks/ended', views.TaskEndedAPIView.as_view()),
    path('api/v1/<slug:username>/whoami', views.MemberRoleAPIView.as_view()),

    path('api/v1/<slug:username>/sendhw', views.HomeworkSendAPIView.as_view()),

    path('api/v1/<slug:username>/students', views.MemberStudentsAPIView.as_view()),
    path('api/v1/<slug:username>/students/<int:task>', views.MemberStudentsByTaskAPIView.as_view()),
    path('api/v1/<slug:username>/homeworks', views.HomeworkAPIView.as_view()),
    path('api/v1/<slug:username>/checkhw', views.HomeworkCheckAPIView.as_view()),
    path('api/v1/<slug:username>/groupedhwinfo', views.HomeworkGroupedAPIView.as_view()),
    path('api/v1/<slug:username>/statistic/<int:limit>', views.StatisticAPIView.as_view()),
    path('api/v1/<slug:username>/expel/<slug:student_username>', views.MemberExpelAPIView.as_view()),
]
