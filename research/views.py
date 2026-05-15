from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from agent.providers import AllProvidersFailed, has_configured_provider, run_research_session
from repositories.models import Repository
from repositories.services import RepositoryService
from research.models import ResearchSession
from research.serializers import (
    ResearchSessionCreateSerializer,
    ResearchSessionSerializer,
)


class ResearchSessionCreateView(APIView):
    def post(self, request):
        serializer = ResearchSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not has_configured_provider():
            return Response(
                {
                    "detail": (
                        "No LLM provider configured. Set at least one API key: "
                        "GROQ_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        repository = RepositoryService.get_or_clone(serializer.validated_data["repo_url"])
        session = ResearchSession.objects.create(
            repository=repository,
            question=serializer.validated_data["question"],
        )

        try:
            run_research_session(session)
        except AllProvidersFailed as exc:
            session.refresh_from_db()
            return Response(
                {
                    "detail": str(exc),
                    "providers_tried": exc.errors,
                    "session_id": session.id,
                    "status": session.status,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        session.refresh_from_db()
        return Response(
            ResearchSessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )


class ResearchSessionDetailView(generics.RetrieveAPIView):
    queryset = ResearchSession.objects.select_related("repository").prefetch_related(
        "tool_calls",
        "findings",
    )
    serializer_class = ResearchSessionSerializer


class RepositorySessionListView(generics.ListAPIView):
    serializer_class = ResearchSessionSerializer

    def get_queryset(self):
        get_object_or_404(Repository, pk=self.kwargs["repo_id"])
        return (
            ResearchSession.objects.filter(repository_id=self.kwargs["repo_id"])
            .select_related("repository")
            .prefetch_related("tool_calls", "findings")
            .order_by("-created_at")
        )
