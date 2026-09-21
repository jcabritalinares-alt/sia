import os, sys, django
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from entregas.views import historial_entregas

rf = RequestFactory()
request = rf.get('/historial/')
user = User.objects.filter(is_superuser=True).first() or User.objects.first()
request.user = user

response = historial_entregas(request)
html = response.content.decode('utf-8')
print("Status code:", response.status_code)
print("HTML length:", len(html))
print("Contains table:", '<table id="tablaHistorial"' in html)
print("Contains modalEliminar:", 'modalEliminarEntrega' in html)
print("Contains modalEditarBeneficiario:", 'modalEditarBeneficiario' in html)
print("Ends with </html>:", html.strip().endswith('</html>'))
