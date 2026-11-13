from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied


class APISessionAuthentication(SessionAuthentication):
    def authenticate_header(self, request):
        return 'Session'

    def enforce_csrf(self, request):
        try:
            super().enforce_csrf(request)
        except PermissionDenied:
            raise PermissionDenied('CSRF verification failed.', code='CSRF_FAILED')


def api_exception_handler(exc, context):
    from rest_framework.views import exception_handler
    response = exception_handler(exc, context)
    if response is None:
        return None
    status = response.status_code
    if status == 400:
        fields = response.data if isinstance(response.data, dict) else {'non_field_errors': response.data}
        fields = {key: value if isinstance(value, list) else [value] for key, value in fields.items()}
        response.data = {'code': 'VALIDATION_ERROR', 'message': 'Please correct the highlighted fields.', 'fields': fields}
    else:
        codes = {401: 'AUTHENTICATION_REQUIRED', 403: 'PERMISSION_DENIED', 404: 'NOT_FOUND', 405: 'METHOD_NOT_ALLOWED', 415: 'UNSUPPORTED_MEDIA_TYPE', 429: 'RATE_LIMITED'}
        code = codes.get(status, 'API_ERROR')
        if getattr(exc, 'get_codes', lambda: None)() == 'CSRF_FAILED':
            code = 'CSRF_FAILED'
        response.data = {'code': code, 'message': str(getattr(exc, 'detail', 'Request failed.'))}
    return response

