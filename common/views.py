
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health_check(request):
    if not settings.DEBUG:
        return JsonResponse(
            {"code": "NOT_FOUND", "message": "Not found"},
            status=404,
        )

    if request.get_host().split(":")[0] not in (
        "localhost",
        "127.0.0.1",
    ):
        return JsonResponse(
            {"code": "NOT_FOUND", "message": "Not found"},
            status=404,
        )

    return JsonResponse({"status": "ok"})
