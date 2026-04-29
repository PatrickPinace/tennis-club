from django import forms
from .models import Article, Category, Comment

class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'lead', 'content', 'image', 'categories']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Wpisz tytuł artykułu'}),
            'lead': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Krótki wstęp zachęcający do czytania...'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'categories': forms.CheckboxSelectMultiple(),
        }
        labels = {
            'title': 'Tytuł',
            'lead': 'Zajawka (wstęp)',
            'content': 'Treść artykułu',
            'image': 'Zdjęcie wyróżniające',
            'categories': 'Kategorie',
        }

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if title:
            # Sprawdź czy istnieje inny artykuł o tym samym tytule (case-insensitive)
            qs = Article.objects.filter(title__iexact=title)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise forms.ValidationError("Artykuł o takim tytule już istnieje. Proszę wybrać inny tytuł.")
        return title


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        labels = {
            'content': 'Twój komentarz'
        }
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Napisz komentarz...', 'class': 'form-control'}),
        }
