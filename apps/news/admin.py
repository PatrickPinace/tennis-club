from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from .models import Article, Category, Comment

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'articles_count')
    prepopulated_fields = {'slug': ('name',)}

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(_articles_count=Count("articles"))
        return queryset

    def articles_count(self, obj):
        return obj._articles_count
    articles_count.short_description = "Liczba artykułów"
    articles_count.admin_order_field = '_articles_count'

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'image_preview', 'author', 'status', 'published_at', 'likes_count', 'comments_count')
    list_filter = ('status', 'categories', 'created_at', 'published_at')
    search_fields = ('title', 'content', 'lead')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    ordering = ('-published_at',)
    autocomplete_fields = ['author']
    list_select_related = ('author',)
    filter_horizontal = ('categories', 'likes')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _likes_count=Count("likes", distinct=True),
            _comments_count=Count("comments", distinct=True)
        )
        return queryset

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: auto;" />', obj.image.url)
        return "-"
    image_preview.short_description = "Zdjęcie"

    def likes_count(self, obj):
        return obj._likes_count
    likes_count.short_description = "Polubienia"
    likes_count.admin_order_field = '_likes_count'

    def comments_count(self, obj):
        return obj._comments_count
    comments_count.short_description = "Komentarze"
    comments_count.admin_order_field = '_comments_count'

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'article', 'short_content', 'created_at', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('content', 'author__username', 'article__title')
    actions = ['approve_comments', 'disapprove_comments']
    list_select_related = ('author', 'article')

    def short_content(self, obj):
        if len(obj.content) > 50:
            return f"{obj.content[:50]}..."
        return obj.content
    short_content.short_description = "Treść"

    def approve_comments(self, request, queryset):
        queryset.update(is_active=True)
    approve_comments.short_description = "Zatwierdź wybrane komentarze"

    def disapprove_comments(self, request, queryset):
        queryset.update(is_active=False)
    disapprove_comments.short_description = "Ukryj wybrane komentarze"
