from django.db import models


class Repository(models.Model):
    url = models.URLField(unique=True)
    name = models.CharField(max_length=255)
    local_clone_path = models.CharField(max_length=1024, blank=True)
    default_branch = models.CharField(max_length=255, default="main")
    last_indexed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name
