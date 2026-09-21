from django.core.cache import cache
from django.utils import timezone

class ActiveUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            cache_key = f'last_seen_{request.user.id}'
            # Guarda en caché que el usuario estuvo activo en este preciso instante (expira en 900s = 15 minutos)
            cache.set(cache_key, timezone.now(), 900)
        
        response = self.get_response(request)
        return response

