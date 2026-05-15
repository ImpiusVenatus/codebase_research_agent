from django.urls import path

from research.views import (
    RepositorySessionListView,
    ResearchSessionCreateView,
    ResearchSessionDetailView,
)


urlpatterns = [
    path("sessions/", ResearchSessionCreateView.as_view(), name="session-create"),
    path("sessions/<int:pk>/", ResearchSessionDetailView.as_view(), name="session-detail"),
    path(
        "repositories/<int:repo_id>/sessions/",
        RepositorySessionListView.as_view(),
        name="repository-sessions",
    ),
]
