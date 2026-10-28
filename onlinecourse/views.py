from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
import logging

# Import all required models
from .models import Course, Lesson, Instructor, Learner, Question, Choice, Submission, Enrollment

# Get an instance of a logger
logger = logging.getLogger(__name__)


def registration_request(request):
    context = {}
    if request.method == 'GET':
        return render(request, 'onlinecourse/user_registration_bootstrap.html', context)
    elif request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']
        user_exist = False
        try:
            User.objects.get(username=username)
            user_exist = True
        except:
            logger.error("New user")
        if not user_exist:
            user = User.objects.create_user(
                username=username, first_name=first_name, last_name=last_name, password=password
            )
            login(request, user)
            return redirect("onlinecourse:index")
        else:
            context['message'] = "User already exists."
            return render(request, 'onlinecourse/user_registration_bootstrap.html', context)


def login_request(request):
    context = {}
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "Invalid username or password."
            return render(request, 'onlinecourse/user_login_bootstrap.html', context)
    else:
        return render(request, 'onlinecourse/user_login_bootstrap.html', context)


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    is_enrolled = False
    if user.id is not None:
        num_results = Enrollment.objects.filter(user=user, course=course).count()
        if num_results > 0:
            is_enrolled = True
    return is_enrolled


# CourseListView
class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]
        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)
        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    is_enrolled = check_if_enrolled(user, course)
    if not is_enrolled and user.is_authenticated:
        Enrollment.objects.create(user=user, course=course, mode='honor')
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(reverse(viewname='onlinecourse:course_details', args=(course.id,)))


def extract_answers(request):
    submitted_answers = []
    for key in request.POST:
        if key.startswith('choice'):
            value = request.POST[key]
            try:
                choice_id = int(value)
                submitted_answers.append(choice_id)
            except (ValueError, TypeError):
                parts = key.split('_')
                if len(parts) > 1:
                    try:
                        submitted_answers.append(int(parts[1]))
                    except (ValueError, TypeError):
                        pass
    for cid in request.POST.getlist('choice') + request.POST.getlist('choices'):
        try:
            submitted_answers.append(int(cid))
        except (ValueError, TypeError):
            pass
    return list(set(submitted_answers))


def submit(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user if request.user.is_authenticated else None
    enrollment = Enrollment.objects.filter(user=user, course=course).first() if user else None

    submission = Submission.objects.create(
        user=user,
        enrollment=enrollment,
        course=course
    )
    submitted_answers = extract_answers(request)
    valid_choices = Choice.objects.filter(id__in=submitted_answers)
    submission.choices.set(valid_choices)
    submission.save()

    return HttpResponseRedirect(reverse(viewname='onlinecourse:show_exam_result', args=(course.id, submission.id,)))


def show_exam_result(request, course_id, submission_id):
    context = {}
    course = get_object_or_404(Course, pk=course_id)
    submission = get_object_or_404(Submission, pk=submission_id)

    total_score = 0
    possible_score = 0
    selected_ids = list(submission.choices.values_list('id', flat=True))

    questions = Question.objects.filter(course=course).distinct()
    if not questions.exists():
        questions = Question.objects.filter(lesson__course=course).distinct()

    for question in questions:
        possible_score += question.grade
        if question.is_get_score(selected_ids):
            total_score += question.grade

    context['course'] = course
    context['grade'] = total_score
    context['possible'] = possible_score
    context['possible_score'] = possible_score
    context['selected_ids'] = selected_ids
    context['submission'] = submission

    return render(request, 'onlinecourse/exam_result_bootstrap.html', context)
