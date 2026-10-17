from django.core.cache import cache
from django.utils import timezone

class ActiveUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self._last_seen_writes = {}

    def __call__(self, request):
        if request.user.is_authenticated:
            user_id = request.user.id
            ahora = timezone.now()
            ultimo_registro = self._last_seen_writes.get(user_id)
            # Solo escribir en la base de datos de caché si pasaron más de 60 segundos
            if not ultimo_registro or (ahora - ultimo_registro).total_seconds() > 60:
                cache_key = f'last_seen_{user_id}'
                cache.set(cache_key, ahora, 900)
                self._last_seen_writes[user_id] = ahora
        
        response = self.get_response(request)
        return response

