import os
import shutil
from datetime import datetime
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings

class Command(BaseCommand):
    help = 'Genera un respaldo completo de la base de datos y archivos de SIA Web'

    def handle(self, *args, **options):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        json_file = os.path.join(backup_dir, f'respaldo_sia_{timestamp}.json')
        
        self.stdout.write(self.style.NOTICE(f'Iniciando respaldo de base de datos...'))

        try:
            with open(json_file, 'w', encoding='utf-8') as f:
                call_command('dumpdata', '--natural-foreign', '--natural-primary', exclude=['contenttypes', 'auth.permission'], stdout=f)
            
            self.stdout.write(self.style.SUCCESS(f' Respaldo JSON generado con éxito: {json_file}'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error generando dumpdata: {str(e)}'))

        # Si existe db.sqlite3 local, realizar copia de seguridad adicional del archivo
        sqlite_file = os.path.join(settings.BASE_DIR, 'db.sqlite3')
        if os.path.exists(sqlite_file):
            sqlite_copy = os.path.join(backup_dir, f'db_copy_{timestamp}.sqlite3')
            try:
                shutil.copy2(sqlite_file, sqlite_copy)
                self.stdout.write(self.style.SUCCESS(f' Copia física de SQLite guardada: {sqlite_copy}'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Error copiando sqlite: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f' Proceso de respaldo completado satisfactoriamente.'))
