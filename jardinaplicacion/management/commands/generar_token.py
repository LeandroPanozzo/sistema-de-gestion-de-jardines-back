# jardinaplicacion/management/commands/generar_token.py

from django.core.management.base import BaseCommand
from rest_framework.authtoken.models import Token
from jardinaplicacion.models import CustomUser

class Command(BaseCommand):
    help = 'Genera tokens de autenticación para usuarios directivos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username específico para generar token',
            required=False
        )
        parser.add_argument(
            '--crear',
            action='store_true',
            help='Crear un nuevo usuario directivo',
        )

    def handle(self, *args, **options):
        if options['crear']:
            self.crear_usuario_directivo()
            return
            
        username = options.get('username')
        
        if username:
            self.generar_token_usuario(username)
        else:
            self.generar_tokens_todos_directivos()

    def crear_usuario_directivo(self):
        """Crear un usuario directivo interactivamente"""
        self.stdout.write("🏫 Crear Usuario Directivo")
        self.stdout.write("=" * 30)
        
        username = input("Username: ")
        email = input("Email: ")
        password = input("Password: ")
        
        try:
            # Verificar si el usuario ya existe
            if CustomUser.objects.filter(username=username).exists():
                self.stdout.write(
                    self.style.ERROR(f'❌ El usuario "{username}" ya existe')
                )
                return
            
            # Crear usuario
            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password,
                es_directivo=True
            )
            
            # Generar token
            token, created = Token.objects.get_or_create(user=user)
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Usuario directivo "{username}" creado')
            )
            self.stdout.write(f'🔑 Token: {token.key}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error: {e}')
            )

    def generar_token_usuario(self, username):
        """Generar token para un usuario específico"""
        try:
            user = CustomUser.objects.get(username=username)
            
            if not user.es_directivo:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  {username} no es directivo')
                )
                return
            
            token, created = Token.objects.get_or_create(user=user)
            status = "🆕 Creado" if created else "✅ Existente"
            
            self.stdout.write(f'{status} - Token para {username}:')
            self.stdout.write(f'🔑 {token.key}')
            
        except CustomUser.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Usuario "{username}" no encontrado')
            )

    def generar_tokens_todos_directivos(self):
        """Generar tokens para todos los usuarios directivos"""
        usuarios_directivos = CustomUser.objects.filter(es_directivo=True)
        
        if not usuarios_directivos.exists():
            self.stdout.write(
                self.style.WARNING('⚠️  No hay usuarios directivos')
            )
            self.stdout.write('Usa: python manage.py generar_token --crear')
            return
        
        self.stdout.write(f'📋 {usuarios_directivos.count()} usuarios directivos encontrados:')
        self.stdout.write('=' * 50)
        
        for user in usuarios_directivos:
            token, created = Token.objects.get_or_create(user=user)
            status = "🆕" if created else "✅"
            
            self.stdout.write(f'{status} {user.username} ({user.email})')
            self.stdout.write(f'   🔑 {token.key}')
            self.stdout.write('')