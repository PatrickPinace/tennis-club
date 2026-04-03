from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.urls import reverse

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nazwa")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="Slug")

    class Meta:
        verbose_name = "Kategoria"
        verbose_name_plural = "Kategorie"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Article(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Szkic'),
        ('published', 'Opublikowany'),
    )

    title = models.CharField(max_length=200, verbose_name="Tytuł")
    slug = models.SlugField(max_length=200, unique=True, verbose_name="Slug")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='articles', verbose_name="Autor")
    content = models.TextField(verbose_name="Treść")
    lead = models.TextField(blank=True, help_text="Krótki wstęp widoczny na liście", verbose_name="Zajawka")
    image = models.ImageField(upload_to='articles/', blank=True, null=True, verbose_name="Zdjęcie wyróżniające")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Utworzono")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Zaktualizowano")
    published_at = models.DateTimeField(blank=True, null=True, verbose_name="Data publikacji")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft', verbose_name="Status")
    categories = models.ManyToManyField(Category, related_name='articles', blank=True, verbose_name="Kategorie")
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='liked_articles', blank=True, verbose_name="Polubienia")

    class Meta:
        verbose_name = "Artykuł"
        verbose_name_plural = "Artykuły"
        ordering = ['-published_at', '-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('news:article_detail', kwargs={'slug': self.slug})


class Comment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments', verbose_name="Artykuł")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comments', verbose_name="Autor")
    content = models.TextField(verbose_name="Treść komentarza")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data dodania")
    is_active = models.BooleanField(default=True, verbose_name="Aktywny")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies', verbose_name="Rodzic")
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='liked_comments', blank=True, verbose_name="Polubienia")
    dislikes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='disliked_comments', blank=True, verbose_name="Anty-polubienia")

    class Meta:
        verbose_name = "Komentarz"
        verbose_name_plural = "Komentarze"
        ordering = ['created_at']

    def __str__(self):
        return f'Komentarz od {self.author} do {self.article}'
