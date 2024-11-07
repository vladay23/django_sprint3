import datetime

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.views.generic import (
    ListView, UpdateView, CreateView, DeleteView, DetailView
)

from .models import Category, Post, Comment
from .forms import PostForm, CommentForm, UserForm

PAGINATOR_VALUE: int = 10
PAGE_NUMBER = "page"


def post_queryset(category_is_published: bool = True):
    return Post.objects.filter(
        is_published=True,
        pub_date__date__lt=datetime.datetime.now(),
        category__is_published=category_is_published
    ).order_by('-pub_date')


@login_required
def simple_view(request):
    return HttpResponse('Страница для залогиненных пользователей!')


def get_page_context(queryset, request):
    paginator = Paginator(queryset, PAGINATOR_VALUE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return {
        'paginator': paginator,
        'page_number': page_number,
        'page_obj': page_obj,
    }


class PostListView(ListView):
    model = Post
    template_name = 'blog/index.html'
    queryset = Post.objects.filter(is_published=True,
                                   category__is_published=True,
                                   pub_date__lte=timezone.now()
                                   ).annotate(comment_count=Count("comments"))
    ordering = '-pub_date'
    paginate_by = 10


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/detail.html'
    pk_url_kwarg = 'pk'

    def dispatch(self, request, *args, **kwargs):
        post = self.get_object()
        if (post.author != request.user
            and (not post.is_published or not post.category.is_published
                 or post.pub_date > timezone.now())):
            raise Http404
        else:
            return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        post = get_object_or_404(Post, pk=self.kwargs['pk'])
        context = super().get_context_data(**kwargs)
        context['form'] = CommentForm()
        context['comments'] = (
            post.comments.select_related('author')
        )
        return context


@login_required
def category_posts(request, category_slug):
    template = 'blog/category.html'
    category = get_object_or_404(
        Category.objects.prefetch_related(
            Prefetch(
                'posts',
                post_queryset()
                .annotate(comment_count=Count('comments')),
            )
        ).filter(slug=category_slug),
        is_published=True,
    )
    context = {
        'category': category,
    }
    context.update(get_page_context(category.posts.all().filter(
                                    category__slug=category_slug), request
                                    ))
    return render(request, template, context)


def profile_detail(request, username):
    template = 'blog/profile.html'
    profile = get_object_or_404(User, username=username)
    posts = Post.objects.all().annotate(
        comment_count=Count('comments')
    ).filter(
        author__username=username,
    ).order_by('-pub_date')

    if not (
            request.user.is_authenticated
            and request.user.username == username
    ):
        posts = posts.filter(is_published=True, pub_date__lte=timezone.now())

    paginator = Paginator(posts, PAGINATOR_VALUE)
    page_number = request.GET.get(PAGE_NUMBER)
    page_obj = paginator.get_page(page_number)
    context = {'profile': profile,
               'page_obj': page_obj}
    return render(request, template, context)


@login_required
def edit_profile(request):
    form = UserForm(request.POST or None, instance=request.user)
    if form.is_valid():
        form.save()
        return redirect('blog:profile', username=request.POST.get('username'))
    return render(request, 'blog/user.html', {'form': form})


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def get_success_url(self):
        return reverse('blog:profile', kwargs={
            'username': self.request.user.username})

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)


class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    template_name = 'blog/create.html'
    form_class = PostForm
    success_url = reverse_lazy('blog:post_detail')

    def dispatch(self, request, *args, **kwargs):
        post = get_object_or_404(Post, pk=kwargs['pk'])
        if post.author != request.user:
            return redirect('blog:post_detail', pk=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('blog:post_detail', kwargs={
            'pk': self.kwargs['pk']})

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)


class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    template_name = 'blog/create.html'
    success_url = reverse_lazy('blog:index')

    def dispatch(self, request, *args, **kwargs):
        publication = get_object_or_404(Post, pk=kwargs['pk'])
        if publication.author != request.user:
            return redirect('blog:post_detail', pk=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = {"instance": self.object}
        return context


class CommentCreateView(LoginRequiredMixin, CreateView):
    object = None
    model = Comment
    form_class = CommentForm
    template_name = 'blog/comment.html'
    success_url = reverse_lazy('blog:post_detail')

    # Переопределяем dispatch()
    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(Post, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    # Переопределяем form_valid()
    def form_valid(self, form):
        form.instance.author = self.request.user
        post_id = self.kwargs['pk']
        post = get_object_or_404(Post, id=post_id)
        form.instance.post = post
        return super().form_valid(form)

    # Переопределяем get_success_url()
    def get_success_url(self):
        return reverse('blog:post_detail', kwargs={
            'pk': self.kwargs['pk']})


class CommentUpdateView(LoginRequiredMixin, UpdateView):
    model = Comment
    form_class = CommentForm
    pk_url_kwarg = 'comment_id'
    template_name = 'blog/comment.html'
    success_url = reverse_lazy('blog:post_detail')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        comment = self.get_object()
        if comment.author != request.user:
            return redirect('blog:post_detail', pk=comment.post_id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('blog:post_detail', kwargs={
            'pk': self.kwargs['pk']})


class CommentDeletelView(LoginRequiredMixin, DeleteView):
    model = Comment
    pk_url_kwarg = 'comment_id'
    template_name = 'blog/comment.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        comment = self.get_object()
        if comment.author != request.user:
            return redirect('blog:post_detail', pk=comment.post_id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('blog:post_detail', kwargs={
            'pk': self.kwargs['pk']})
