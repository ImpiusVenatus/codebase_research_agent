from django.db import models


class ResearchSession(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    repository = models.ForeignKey(
        "repositories.Repository",
        related_name="sessions",
        on_delete=models.CASCADE,
    )
    question = models.TextField()
    final_answer = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.repository.name}: {self.question[:80]}"


class ToolCall(models.Model):
    session = models.ForeignKey(
        ResearchSession,
        related_name="tool_calls",
        on_delete=models.CASCADE,
    )
    step_number = models.IntegerField()
    tool_name = models.CharField(max_length=255)
    tool_input = models.JSONField()
    tool_output = models.TextField()
    duration_ms = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["step_number"]

    def __str__(self) -> str:
        return f"{self.session_id} #{self.step_number}: {self.tool_name}"


class Finding(models.Model):
    session = models.ForeignKey(
        ResearchSession,
        related_name="findings",
        on_delete=models.CASCADE,
    )
    file_path = models.CharField(max_length=1024)
    line_start = models.IntegerField(null=True)
    line_end = models.IntegerField(null=True)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.file_path}: {self.note[:80]}"
