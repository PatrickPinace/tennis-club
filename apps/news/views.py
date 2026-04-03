from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.db.models import Q
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Article, Comment
from .forms import ArticleForm, CommentForm
from django.template.loader import render_to_string
from django.core.files.storage import default_storage
from django.views.decorators.csrf import csrf_exempt # Not strictly needed if we pass token, but good to have option or just use standard
# Actually we will use standard protection and pass token.

@require_POST
@login_required
def upload_image(request):
    file = request.FILES.get('file')
    if file:
        # Validate file type
        if not file.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
             return JsonResponse({'error': 'Unsupported file type'}, status=400)
        
        # Save file
        file_path = default_storage.save(f'uploads/{file.name}', file)
        file_url = default_storage.url(file_path)
        
        return JsonResponse({'location': file_url})
    return JsonResponse({'error': 'No file uploaded'}, status=400)

class ArticleListView(ListView):
    model = Article
    template_name = 'news/article_list.html'
    context_object_name = 'articles'
    paginate_by = 10

    def get_queryset(self):
        queryset = Article.objects.filter(status='published')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | 
                Q(lead__icontains=query) |
                Q(content__icontains=query)
            )
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['my_drafts'] = Article.objects.filter(author=self.request.user, status='draft')
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(self.request, 'news/partials/article_list_content.html', context)
        return super().render_to_response(context, **response_kwargs)

class ArticleDetailView(DetailView):
    model = Article
    template_name = 'news/article_detail.html'
    context_object_name = 'article'
    query_pk_and_slug = True

    def get_queryset(self):
        # Allow author to see their drafts via detail view
        if self.request.user.is_authenticated:
             return Article.objects.filter(Q(status='published') | Q(author=self.request.user))
        return Article.objects.filter(status='published')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = self.object
        context['comments'] = article.comments.filter(is_active=True).order_by('-created_at')
        if self.request.user.is_authenticated:
            context['comment_form'] = CommentForm()
            context['is_liked'] = article.likes.filter(id=self.request.user.id).exists()
        return context


@require_POST
@login_required
def add_comment(request, slug):
    article = get_object_or_404(Article, slug=slug)
    form = CommentForm(request.POST)
    parent_id = request.POST.get('parent_id')
    
    if form.is_valid():
        comment = form.save(commit=False)
        comment.article = article
        comment.author = request.user
        
        if parent_id:
            parent_comment = get_object_or_404(Comment, id=parent_id)
            comment.parent = parent_comment
            
        comment.save()
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            comment_html = render_to_string('news/partials/comment.html', {'comment': comment})
            return JsonResponse({'html': comment_html, 'count': article.comments.count()})
            
    return redirect('news:article_detail', slug=slug)

@require_POST
@login_required
def react_to_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    action = request.POST.get('action') # 'like' or 'dislike'
    user = request.user
    
    if action == 'like':
        if comment.dislikes.filter(id=user.id).exists():
            comment.dislikes.remove(user)
        
        if comment.likes.filter(id=user.id).exists():
            comment.likes.remove(user)
            liked = False
        else:
            comment.likes.add(user)
            liked = True
        disliked = False
            
    elif action == 'dislike':
        if comment.likes.filter(id=user.id).exists():
            comment.likes.remove(user)

        if comment.dislikes.filter(id=user.id).exists():
            comment.dislikes.remove(user)
            disliked = False
        else:
            comment.dislikes.add(user)
            disliked = True
        liked = False
    
    return JsonResponse({
        'likes_count': comment.likes.count(),
        'dislikes_count': comment.dislikes.count(),
        'liked': liked,
        'disliked': disliked
    })

@require_POST
@login_required
def like_article(request, slug):
    article = get_object_or_404(Article, slug=slug)
    liked = False
    if article.likes.filter(id=request.user.id).exists():
        article.likes.remove(request.user)
        liked = False
    else:
        article.likes.add(request.user)
        liked = True
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'liked': liked, 'count': article.likes.count()})
    
    return redirect('news:article_detail', slug=slug)

class ArticleCreateView(LoginRequiredMixin, CreateView):
    model = Article
    form_class = ArticleForm
    template_name = 'news/article_form.html'
    success_url = reverse_lazy('news:article_list')

    def form_valid(self, form):
        form.instance.author = self.request.user
        action = self.request.POST.get('action')
        
        if action == 'publish':
            form.instance.status = 'published'
            form.instance.published_at = timezone.now()
        else:
            form.instance.status = 'draft'
            
        return super().form_valid(form)

class ArticleUpdateView(LoginRequiredMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = 'news/article_form.html'
    success_url = reverse_lazy('news:article_list')

    def get_queryset(self):
        # User can only edit their own articles
        return Article.objects.filter(author=self.request.user)

    def form_valid(self, form):
        action = self.request.POST.get('action')
        
        if action == 'publish':
            form.instance.status = 'published'
            if not form.instance.published_at:
                form.instance.published_at = timezone.now()
        else:
            form.instance.status = 'draft'
            
        return super().form_valid(form)
