from django.db import models


class Member(models.Model):
    class Role(models.IntegerChoices):
        ADMIN = 1, "админ"
        TUTOR = 2, "ментор"
        STUDENT = 3, "студент"

    username = models.SlugField(unique=True, db_index=True)
    role = models.IntegerField(choices=Role.choices, default=Role.STUDENT)
    gsheets_id = models.IntegerField(null=True)
    tutor = models.ForeignKey('Member', on_delete=models.SET_NULL, related_name='students', null=True)

    def __str__(self):
        return self.username


class Task(models.Model):
    start_date = models.DateField()
    end_date = models.DateField()


class Homework(models.Model):
    url = models.URLField(max_length=255)
    mark = models.FloatField(null=True)
    owner = models.ForeignKey('Member', on_delete=models.CASCADE, related_name='hws')
    task = models.ForeignKey('Task', on_delete=models.CASCADE, related_name='hws')


class Statistic(models.Model):
    sum = models.FloatField(default=0)
    passed = models.IntegerField(default=-1)
    project = models.FloatField(null=True)
    student = models.OneToOneField('Member', on_delete=models.CASCADE, related_name='statistic')
