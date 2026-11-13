from rest_framework.throttling import SimpleRateThrottle


class AccountsThrottle(SimpleRateThrottle):
    scope = 'accounts'

    def get_cache_key(self, request, view):
        self.scope = view.throttle_scope
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        # REMOTE_ADDR only: do not trust client-controlled forwarded headers.
        identity = str(request.user.pk) if request.user.is_authenticated else request.META.get('REMOTE_ADDR', '')
        return self.cache_format % {'scope': self.scope, 'ident': identity}
