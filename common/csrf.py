from django.http import JsonResponse


def csrf_failure(request, reason=""):
    return JsonResponse(
        {
            "code": "CSRF_FAILED",
            "message": "CSRF verification failed.",
        },
        status=403,
    )