from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, logout, authenticate
from django.utils import timezone
from django.db.models import Q
from datetime import date
from django.shortcuts import get_object_or_404
import secrets
from django.core.management import call_command
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from io import StringIO
import sys
import string
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from .models import (
    CustomUser, CicloLectivo, Curso, Alumno, Familiar,
    RegistroAsistenciaMaestro, RegistroRetiroAlumno, CuotaCurso, PagoCuota,
    ConfiguracionSistema, RegistroAsistenciaAlumno,AvisoDirectivo, DeudorCuota, PasswordResetToken,generate_random_token
)
from .serializers import (
    CustomUserSerializer, LoginSerializer, CicloLectivoSerializer,
    CursoSerializer, AlumnoSerializer, FamiliarSerializer, ProcesamientoVencimientosSerializer, ProcesarAusenciasMasivasSerializer,
    RegistroAsistenciaMaestroSerializer, RegistroRetiroAlumnoSerializer,
    CuotaCursoSerializer, PagoCuotaSerializer, MaestroAsignacionSerializer,
    RegistrarIngresoSerializer, RegistrarSalidaSerializer, HabilitarUsuarioSerializer,
    ConfiguracionSistemaSerializer,RegistroAsistenciaAlumnoSerializer,AvisoDirectivoSerializer,  # Agregar este
    ProcesarAvisoSerializer,AvisarDirectivoSerializer,  # Add this line
    AvisoDirectivoSerializer,   # Add this line
    ProcesarAvisoSerializer,  DeudorCuotaSerializer,  ForgotPasswordSerializer, ResetPasswordSerializer, 
    ForgotUsernameSerializer, MarcarAusenteSerializer
)


class IsDirectivo(permissions.BasePermission):
    """Permiso para directivos"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.es_directivo


class IsMaestro(permissions.BasePermission):
    """Permiso para maestros"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.es_maestro


class IsMaestroOrDirectivo(permissions.BasePermission):
    """Permiso para maestros o directivos"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.es_maestro or request.user.es_directivo)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request):
    """Vista de login"""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # Crear o obtener token
        token, created = Token.objects.get_or_create(user=user)
        
        # Login del usuario
        login(request, user)
        
        return Response({
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'es_maestro': user.es_maestro,
                'es_directivo': user.es_directivo,
            }
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """Vista de logout"""
    try:
        # Eliminar el token del usuario
        if hasattr(request.user, 'auth_token'):
            request.user.auth_token.delete()
    except Exception:
        pass
    
    logout(request)
    return Response({'message': 'Logout exitoso'})


class ConfiguracionSistemaViewSet(viewsets.ModelViewSet):
    queryset = ConfiguracionSistema.objects.all()
    serializer_class = ConfiguracionSistemaSerializer
    permission_classes = [IsDirectivo]
    
    @action(detail=False, methods=['get'])
    def actual(self, request):
        """Obtener la configuración actual del sistema"""
        config = ConfiguracionSistema.get_configuracion()
        serializer = self.get_serializer(config)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def toggle_registro_asistencia(self, request):
        """Habilitar/deshabilitar el registro de asistencia"""
        config = ConfiguracionSistema.get_configuracion()
        config.registro_asistencia_habilitado = not config.registro_asistencia_habilitado
        config.actualizado_por = request.user
        config.save()
        
        estado = "habilitado" if config.registro_asistencia_habilitado else "deshabilitado"
        return Response({
            'message': f'Registro de asistencia {estado} exitosamente',
            'registro_asistencia_habilitado': config.registro_asistencia_habilitado
        })
    
    @action(detail=False, methods=['post'])
    def configurar_registro_asistencia(self, request):
        """Configurar específicamente el estado del registro de asistencia"""
        habilitar = request.data.get('habilitar', True)
        
        config = ConfiguracionSistema.get_configuracion()
        config.registro_asistencia_habilitado = habilitar
        config.actualizado_por = request.user
        config.save()
        
        estado = "habilitado" if habilitar else "deshabilitado"
        return Response({
            'message': f'Registro de asistencia {estado} exitosamente',
            'registro_asistencia_habilitado': config.registro_asistencia_habilitado
        })


class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        """
        Permisos personalizados:
        - Crear: Cualquier usuario (registro público)
        - Actualizar: Usuarios autenticados
        - Eliminar: Solo directivos
        - Listar/Detalle: Solo usuarios autenticados
        """
        if self.action == 'destroy':
            permission_classes = [IsDirectivo]
        elif self.action == 'create':
            # Permitir creación sin autenticación (registro público)
            permission_classes = [permissions.AllowAny]
        elif self.action in ['update', 'partial_update']:
            # Permitir actualización a usuarios autenticados
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    @action(detail=True, methods=['post'], permission_classes=[IsDirectivo])
    def habilitar(self, request, pk=None):
        """Habilitar usuario como maestro/directivo"""
        user = self.get_object()
        serializer = HabilitarUsuarioSerializer(data=request.data)
        
        if serializer.is_valid():
            if 'es_maestro' in serializer.validated_data:
                user.es_maestro = serializer.validated_data['es_maestro']
            if 'es_directivo' in serializer.validated_data:
                user.es_directivo = serializer.validated_data['es_directivo']
            user.save()
            
            return Response({
                'message': 'Usuario habilitado correctamente',
                'user': CustomUserSerializer(user).data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    @action(detail=False, methods=['get'])
    def check_username(self, request):
        """Verificar si un nombre de usuario está disponible"""
        username = request.query_params.get('username')
        exclude_user_id = request.query_params.get('exclude_user_id')
        
        if not username:
            return Response({'error': 'Username parameter is required'}, 
                        status=status.HTTP_400_BAD_REQUEST)
        
        # Crear query base
        query = CustomUser.objects.filter(username=username)
        
        # Excluir usuario actual si se proporciona el ID
        if exclude_user_id:
            try:
                query = query.exclude(id=int(exclude_user_id))
            except ValueError:
                pass
        
        available = not query.exists()
        
        return Response({
            'available': available,
            'username': username
        })

class CicloLectivoViewSet(viewsets.ModelViewSet):
    queryset = CicloLectivo.objects.all()
    serializer_class = CicloLectivoSerializer
    permission_classes = [IsDirectivo]


class CursoViewSet(viewsets.ModelViewSet):
    queryset = Curso.objects.all()
    serializer_class = CursoSerializer
    
    def get_permissions(self):
        """Solo directivos pueden crear, actualizar y eliminar cursos"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsDirectivo]
        else:
            permission_classes = [IsMaestroOrDirectivo]
        return [permission() for permission in permission_classes]
    
    @action(detail=True, methods=['post'], permission_classes=[IsDirectivo])
    def asignar_maestro(self, request, pk=None):
        """Asignar o desasignar maestro a un curso"""
        curso = self.get_object()
        serializer = MaestroAsignacionSerializer(data=request.data)
        
        if serializer.is_valid():
            maestro_id = serializer.validated_data['maestro_id']
            accion = serializer.validated_data['accion']
            
            try:
                # Buscar usuario que sea maestro (puede ser también directivo)
                maestro = CustomUser.objects.get(id=maestro_id, es_maestro=True)
                
                if accion == 'asignar':
                    curso.maestros.add(maestro)
                    message = f'Maestro {maestro.first_name} {maestro.last_name} asignado al curso'
                else:
                    curso.maestros.remove(maestro)
                    message = f'Maestro {maestro.first_name} {maestro.last_name} desasignado del curso'
                
                return Response({'message': message})
            except CustomUser.DoesNotExist:
                return Response(
                    {'error': 'Usuario no encontrado o no es maestro'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    @action(detail=False, methods=['post'], permission_classes=[IsDirectivo])
    def procesar_vencimientos_todos_cursos(self, request):
        """
        Procesa vencimientos de cuotas para todos los cursos
        """
        fecha_param = request.data.get('fecha')
        if fecha_param:
            try:
                fecha = datetime.strptime(fecha_param, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            fecha = timezone.now().date()
        
        try:
            resultado = CuotaCurso.procesar_vencimientos_masivos(fecha)
            return Response(resultado)
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'Error al procesar vencimientos: {str(e)}',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    @action(detail=True, methods=['post'], permission_classes=[IsDirectivo])
    def generar_cuotas_año(self, request, pk=None):
        """Generar cuotas para todo el año lectivo"""
        curso = self.get_object()
        año = request.data.get('año', timezone.now().year)
        
        try:
            cuotas_creadas = 0
            cuotas_existentes = 0
            
            for mes in range(1, 13):  # Enero a Diciembre
                cuota, created = CuotaCurso.objects.get_or_create(
                    curso=curso,
                    mes=mes,
                    año=año,
                    defaults={
                        'monto': curso.cuota_mensual,
                        'fecha_vencimiento': curso.get_fecha_vencimiento(mes, año)
                    }
                )
                
                if created:
                    cuotas_creadas += 1
                else:
                    cuotas_existentes += 1
            
            return Response({
                'message': f'Cuotas generadas para {curso.nombre} - Año {año}',
                'cuotas_creadas': cuotas_creadas,
                'cuotas_existentes': cuotas_existentes
            })
            
        except Exception as e:
            return Response(
                {'error': f'Error al generar cuotas: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    @action(detail=False, methods=['get'], permission_classes=[IsMaestro])
    def mis_cursos(self, request):
        """Obtener los cursos asignados al maestro actual"""
        cursos = self.queryset.filter(maestros=request.user)
        serializer = self.get_serializer(cursos, many=True)
        return Response(serializer.data)
    @action(detail=True, methods=['post'], permission_classes=[IsDirectivo])
    def procesar_ausencias_curso(self, request, pk=None):
        """Procesar ausencias automáticas para un curso específico"""
        curso = self.get_object()
        
        fecha_param = request.data.get('fecha')
        if fecha_param:
            try:
                fecha = datetime.strptime(fecha_param, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            fecha = timezone.now().date()
        
        ausencias_marcadas, mensaje = curso.marcar_ausencias_maestros_automaticas(fecha)
        
        return Response({
            'curso': curso.nombre,
            'fecha': fecha.strftime('%Y-%m-%d'),
            'ausencias_marcadas': ausencias_marcadas,
            'mensaje': mensaje
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsDirectivo])
    def cursos_con_ausencias(self, request):
        """Obtener cursos que tienen maestros ausentes en una fecha"""
        fecha_param = request.query_params.get('fecha')
        
        if fecha_param:
            try:
                fecha = datetime.strptime(fecha_param, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            fecha = timezone.now().date()
        
        # Obtener cursos con maestros ausentes
        cursos_con_ausencias = self.queryset.filter(
            registros_asistencia_maestros__fecha=fecha,
            registros_asistencia_maestros__ausente=True
        ).distinct()
        
        resultado = []
        for curso in cursos_con_ausencias:
            maestros_ausentes = curso.registros_asistencia_maestros.filter(
                fecha=fecha,
                ausente=True
            )
            
            resultado.append({
                'curso_id': curso.id,
                'curso_nombre': curso.nombre,
                'turno': curso.turno,
                'horario': curso.horario,
                'maestros_ausentes': [
                    {
                        'maestro_id': reg.maestro.id,
                        'maestro_nombre': f"{reg.maestro.first_name} {reg.maestro.last_name}"
                    }
                    for reg in maestros_ausentes
                ]
            })
        
        return Response({
            'fecha': fecha.strftime('%Y-%m-%d'),
            'total_cursos_afectados': len(resultado),
            'cursos': resultado
        })


class AlumnoViewSet(viewsets.ModelViewSet):
    serializer_class = AlumnoSerializer
    permission_classes = [IsMaestroOrDirectivo]
    queryset = Alumno.objects.all()

    def get_queryset(self):
        """Filtrar alumnos según el rol del usuario con prefetch de familiares"""
        base_queryset = Alumno.objects.prefetch_related('familiares')
        
        if self.request.user.es_directivo:
            return base_queryset.all()
        elif self.request.user.es_maestro:
            # Los maestros solo ven alumnos de sus cursos
            return base_queryset.filter(curso__maestros=self.request.user)
        return base_queryset.none()
    
    def update(self, request, *args, **kwargs):
        """Override update method to ensure proper permissions"""
        instance = self.get_object()
        
        # Verificar permisos específicos para la actualización
        if request.user.es_maestro:
            # Los maestros solo pueden actualizar alumnos de sus cursos
            if not instance.curso or not instance.curso.maestros.filter(id=request.user.id).exists():
                return Response(
                    {"detail": "No tienes permisos para actualizar este alumno."}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        elif not request.user.es_directivo:
            return Response(
                {"detail": "No tienes permisos para actualizar alumnos."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Proceder con la actualización normal
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}
        
        return Response(serializer.data)
    
    def partial_update(self, request, *args, **kwargs):
        """Override partial_update method"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'], permission_classes=[IsMaestro])
    def mis_alumnos(self, request):
        """Obtener alumnos de los cursos del maestro actual con sus familiares"""
        alumnos = Alumno.objects.filter(
            curso__maestros=request.user
        ).prefetch_related('familiares')
        
        serializer = self.get_serializer(alumnos, many=True)
        return Response(serializer.data)
    
class FamiliarViewSet(viewsets.ModelViewSet):
    queryset = Familiar.objects.all()
    serializer_class = FamiliarSerializer
    permission_classes = [IsMaestroOrDirectivo]
    
    def get_queryset(self):
        """Filtrar familiares según el rol del usuario"""
        if self.request.user.es_directivo:
            return self.queryset
        elif self.request.user.es_maestro:
            # Los maestros solo ven familiares de alumnos de sus cursos
            return self.queryset.filter(alumno__curso__maestros=self.request.user)
        return self.queryset.none()
    
    @action(detail=False, methods=['get'], permission_classes=[IsMaestro])
    def mis_familiares(self, request):
        """Obtener familiares de alumnos de los cursos del maestro actual"""
        familiares = Familiar.objects.filter(
            alumno__curso__maestros=request.user
        ).select_related('alumno')
        
        serializer = self.get_serializer(familiares, many=True)
        return Response(serializer.data)


import logging
logger = logging.getLogger(__name__)

class RegistroAsistenciaMaestroViewSet(viewsets.ModelViewSet):
    queryset = RegistroAsistenciaMaestro.objects.all()
    serializer_class = RegistroAsistenciaMaestroSerializer
    permission_classes = [IsMaestroOrDirectivo]
    
    def get_queryset(self):
        """Los maestros solo ven sus propios registros"""
        if self.request.user.es_directivo:
            return self.queryset
        elif self.request.user.es_maestro:
            return self.queryset.filter(maestro=self.request.user)
        return self.queryset.none()
    
    @action(detail=False, methods=['get'])
    def estado_registro(self, request):
        """Verificar si el registro de asistencia está habilitado"""
        config = ConfiguracionSistema.get_configuracion()
        return Response({
            'registro_habilitado': config.registro_asistencia_habilitado,
            'message': 'Registro de asistencia habilitado' if config.registro_asistencia_habilitado 
                      else 'Registro de asistencia deshabilitado por el directivo'
        })
    
    @action(detail=False, methods=['get'])
    def mis_registros_hoy(self, request):
        """Obtener registros de asistencia del maestro para hoy"""
        fecha_hoy = timezone.now().date()
        registros = self.get_queryset().filter(fecha=fecha_hoy)
        serializer = self.get_serializer(registros, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], permission_classes=[IsMaestro])
    def registrar_ingreso(self, request):
        """Registrar hora de ingreso del maestro para un curso específico"""
        logger.info(f"Datos recibidos: {request.data}")
        logger.info(f"Usuario: {request.user}")
        
        # Verificar si el registro está habilitado
        config = ConfiguracionSistema.get_configuracion()
        if not config.registro_asistencia_habilitado:
            return Response(
                {'error': 'El registro de asistencia está deshabilitado por el directivo'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = RegistrarIngresoSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            curso_id = serializer.validated_data['curso_id']
            hora_ingreso = serializer.validated_data['hora_ingreso']
            fecha_hoy = timezone.now().date()
            
            try:
                curso = Curso.objects.get(id=curso_id)
            except Curso.DoesNotExist:
                return Response(
                    {'error': 'El curso no existe'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Verificar si ya existe un registro para hoy y este curso
            registro, created = RegistroAsistenciaMaestro.objects.get_or_create(
                maestro=request.user,
                curso=curso,
                fecha=fecha_hoy,
                defaults={'hora_ingreso': hora_ingreso}
            )
            
            if not created:
                if registro.hora_ingreso:
                    return Response(
                        {'error': f'Ya registraste tu ingreso para el curso {curso.nombre} hoy'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                else:
                    # Si existe el registro pero sin hora de ingreso, actualizarlo
                    registro.hora_ingreso = hora_ingreso
                    registro.save()
            
            return Response({
                'message': f'Ingreso registrado correctamente para el curso {curso.nombre}',
                'registro': RegistroAsistenciaMaestroSerializer(registro).data
            })
        else:
            logger.error(f"Errores de validación: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    @action(detail=False, methods=['post'], permission_classes=[IsMaestro])
    def avisar_directivo_ingreso(self, request):
        """Avisar al directivo sobre necesidad de registrar ingreso"""
        serializer = AvisarDirectivoSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            curso_id = serializer.validated_data['curso_id']
            fecha_hoy = timezone.now().date()
            hora_actual = timezone.now().time()  # CAPTURAR HORA ACTUAL
            
            try:
                curso = Curso.objects.get(id=curso_id)
            except Curso.DoesNotExist:
                return Response(
                    {'error': 'El curso no existe'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Crear o actualizar aviso para directivos
            aviso, created = AvisoDirectivo.objects.get_or_create(
                maestro=request.user,
                curso=curso,
                fecha=fecha_hoy,
                tipo='ingreso',
                defaults={
                    'procesado': False,
                    'hora_solicitada': hora_actual  # GUARDAR HORA ACTUAL
                }
            )
            
            if not created and aviso.procesado:
                return Response(
                    {'error': 'Ya existe un aviso procesado para este curso hoy'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Si el aviso ya existía pero no estaba procesado, actualizar la hora
            if not created:
                aviso.hora_solicitada = hora_actual
                aviso.save()
            
            return Response({
                'message': f'Aviso enviado a directivos para registrar tu ingreso en {curso.nombre} a las {hora_actual.strftime("%H:%M")}'
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[IsMaestro])
    def avisar_directivo_salida(self, request):
        """Avisar al directivo sobre necesidad de registrar salida"""
        serializer = AvisarDirectivoSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            curso_id = serializer.validated_data['curso_id']
            fecha_hoy = timezone.now().date()
            hora_actual = timezone.now().time()  # CAPTURAR HORA ACTUAL
            
            try:
                curso = Curso.objects.get(id=curso_id)
            except Curso.DoesNotExist:
                return Response(
                    {'error': 'El curso no existe'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Verificar que tenga ingreso registrado
            try:
                registro = RegistroAsistenciaMaestro.objects.get(
                    maestro=request.user,
                    curso=curso,
                    fecha=fecha_hoy
                )
                if not registro.hora_ingreso:
                    return Response(
                        {'error': 'Debes registrar tu ingreso primero'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except RegistroAsistenciaMaestro.DoesNotExist:
                return Response(
                    {'error': 'Debes registrar tu ingreso primero'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Crear aviso para directivos
            aviso, created = AvisoDirectivo.objects.get_or_create(
                maestro=request.user,
                curso=curso,
                fecha=fecha_hoy,
                tipo='salida',
                defaults={
                    'procesado': False,
                    'hora_solicitada': hora_actual  # GUARDAR HORA ACTUAL
                }
            )
            
            if not created and aviso.procesado:
                return Response(
                    {'error': 'Ya existe un aviso procesado para este curso hoy'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Si el aviso ya existía pero no estaba procesado, actualizar la hora
            if not created:
                aviso.hora_solicitada = hora_actual
                aviso.save()
            
            return Response({
                'message': f'Aviso enviado a directivos para registrar tu salida de {curso.nombre} a las {hora_actual.strftime("%H:%M")}'
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    
    @action(detail=False, methods=['post'], permission_classes=[IsMaestro])
    def registrar_salida(self, request):
        """Registrar hora de salida del maestro para un curso específico"""
        logger.info(f"Datos recibidos para salida: {request.data}")
        
        # Verificar si el registro está habilitado
        config = ConfiguracionSistema.get_configuracion()
        if not config.registro_asistencia_habilitado:
            return Response(
                {'error': 'El registro de asistencia está deshabilitado por el directivo'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = RegistrarSalidaSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            # Solo acceder a validated_data si la validación fue exitosa
            curso_id = serializer.validated_data['curso_id']
            hora_salida = serializer.validated_data['hora_salida']
            fecha_hoy = timezone.now().date()
            
            try:
                curso = Curso.objects.get(id=curso_id)
            except Curso.DoesNotExist:
                return Response(
                    {'error': 'El curso no existe'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            try:
                registro = RegistroAsistenciaMaestro.objects.get(
                    maestro=request.user,
                    curso=curso,
                    fecha=fecha_hoy
                )
                
                if not registro.hora_ingreso:
                    return Response(
                        {'error': f'Debes registrar tu ingreso para el curso {curso.nombre} primero'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if registro.hora_salida:
                    return Response(
                        {'error': f'Ya registraste tu salida para el curso {curso.nombre} hoy'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                registro.hora_salida = hora_salida
                registro.save()
                
                return Response({
                    'message': f'Salida registrada correctamente para el curso {curso.nombre}',
                    'registro': RegistroAsistenciaMaestroSerializer(registro).data
                })
                
            except RegistroAsistenciaMaestro.DoesNotExist:
                return Response(
                    {'error': f'Debes registrar tu ingreso para el curso {curso.nombre} primero'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Retornar errores de validación directamente
            logger.error(f"Errores de validación en salida: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    @action(detail=False, methods=['post'], permission_classes=[IsDirectivo])
    def procesar_ausencias_automaticas(self, request):
        """Procesar ausencias automáticas para una fecha específica"""
        serializer = ProcesarAusenciasMasivasSerializer(data=request.data)
        
        if serializer.is_valid():
            fecha = serializer.validated_data.get('fecha', timezone.now().date())
            
            # Procesar ausencias masivas
            resultado = Curso.marcar_ausencias_maestros_masivas(fecha)
            
            return Response(resultado)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], permission_classes=[IsDirectivo])
    def reporte_ausencias(self, request):
        """Obtener reporte de ausencias por fecha"""
        fecha_param = request.query_params.get('fecha')
        
        if fecha_param:
            try:
                fecha = datetime.strptime(fecha_param, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            fecha = timezone.now().date()
        
        # Obtener registros de ausencias para la fecha
        ausencias = self.queryset.filter(fecha=fecha, ausente=True)
        
        # Organizar por curso
        ausencias_por_curso = {}
        for ausencia in ausencias:
            curso_nombre = ausencia.curso.nombre
            if curso_nombre not in ausencias_por_curso:
                ausencias_por_curso[curso_nombre] = []
            
            ausencias_por_curso[curso_nombre].append({
                'maestro_nombre': f"{ausencia.maestro.first_name} {ausencia.maestro.last_name}",
                'curso_horario': ausencia.curso.horario,
                'turno': ausencia.curso.turno
            })
        
        return Response({
            'fecha': fecha.strftime('%Y-%m-%d'),
            'total_ausencias': ausencias.count(),
            'ausencias_por_curso': ausencias_por_curso
        })
    
    @action(detail=False, methods=['get'])
    def mis_ausencias(self, request):
        """Obtener ausencias del maestro actual"""
        if not request.user.es_maestro:
            return Response(
                {'error': 'Solo maestros pueden ver sus ausencias'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Parámetros opcionales
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin = request.query_params.get('fecha_fin')
        
        ausencias = self.queryset.filter(maestro=request.user, ausente=True)
        
        if fecha_inicio:
            try:
                fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
                ausencias = ausencias.filter(fecha__gte=fecha_inicio)
            except ValueError:
                return Response(
                    {'error': 'Formato de fecha_inicio inválido. Use YYYY-MM-DD'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if fecha_fin:
            try:
                fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
                ausencias = ausencias.filter(fecha__lte=fecha_fin)
            except ValueError:
                return Response(
                    {'error': 'Formato de fecha_fin inválido. Use YYYY-MM-DD'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        serializer = self.get_serializer(ausencias, many=True)
        return Response({
            'total_ausencias': ausencias.count(),
            'ausencias': serializer.data
        })

    @action(detail=False, methods=['get'], permission_classes=[IsDirectivo])
    def cursos_en_horario(self, request):
        """Obtener cursos que están en horario actual con sus maestros"""
        from datetime import datetime, time
        
        hora_actual = timezone.now().time()
        fecha_hoy = timezone.now().date()
        
        # Obtener cursos que están en horario
        cursos_en_horario = []
        
        for curso in Curso.objects.all():
            # Parsear el horario del curso (formato: "08:00 - 12:00")
            try:
                horario_parts = curso.horario.split(' - ')
                if len(horario_parts) == 2:
                    hora_inicio_str = horario_parts[0].strip()
                    hora_fin_str = horario_parts[1].strip()
                    
                    # Convertir a objetos time
                    hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M').time()
                    hora_fin = datetime.strptime(hora_fin_str, '%H:%M').time()
                    
                    # Verificar si está en horario
                    if hora_inicio <= hora_actual <= hora_fin:
                        # Obtener maestros del curso con su estado de asistencia
                        maestros_info = []
                        
                        for maestro in curso.maestros.all():
                            # Buscar registro de hoy
                            try:
                                registro = RegistroAsistenciaMaestro.objects.get(
                                    maestro=maestro,
                                    curso=curso,
                                    fecha=fecha_hoy
                                )
                                estado_asistencia = registro.estado_asistencia
                                ya_tiene_registro = True
                            except RegistroAsistenciaMaestro.DoesNotExist:
                                estado_asistencia = 'sin_registro'
                                ya_tiene_registro = False
                            
                            maestros_info.append({
                                'id': maestro.id,
                                'first_name': maestro.first_name,
                                'last_name': maestro.last_name,
                                'ya_tiene_registro': ya_tiene_registro,
                                'estado_asistencia': estado_asistencia
                            })
                        
                        if maestros_info:  # Solo incluir cursos que tienen maestros
                            cursos_en_horario.append({
                                'id': curso.id,
                                'nombre': curso.nombre,
                                'horario': curso.horario,
                                'turno': curso.turno,
                                'maestros': maestros_info
                            })
                            
            except (ValueError, AttributeError) as e:
                logger.warning(f"Error parsing horario for curso {curso.nombre}: {e}")
                continue
        
        return Response(cursos_en_horario)

    @action(detail=False, methods=['post'], permission_classes=[IsDirectivo])
    def marcar_ausente(self, request):
        """Marcar un maestro como ausente en un curso específico"""
        serializer = MarcarAusenteSerializer(data=request.data)
        
        if serializer.is_valid():
            maestro_id = serializer.validated_data['maestro_id']
            curso_id = serializer.validated_data['curso_id']
            fecha_hoy = timezone.now().date()
            
            try:
                maestro = CustomUser.objects.get(id=maestro_id, es_maestro=True)
                curso = Curso.objects.get(id=curso_id)
            except (CustomUser.DoesNotExist, Curso.DoesNotExist):
                return Response(
                    {'error': 'Maestro o curso no encontrado'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Verificar que el maestro esté asignado al curso
            if not curso.maestros.filter(id=maestro_id).exists():
                return Response(
                    {'error': 'El maestro no está asignado a este curso'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Crear o actualizar registro como ausente
            registro, created = RegistroAsistenciaMaestro.objects.get_or_create(
                maestro=maestro,
                curso=curso,
                fecha=fecha_hoy,
                defaults={'ausente': True}
            )
            
            if not created:
                if registro.ausente:
                    return Response(
                        {'error': 'El maestro ya está marcado como ausente para este curso hoy'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Si ya tenía registros de ingreso/salida, mantenerlos pero marcar como ausente
                registro.ausente = True
                registro.save()
            
            return Response({
                'message': f'{maestro.first_name} {maestro.last_name} marcado como ausente en {curso.nombre}',
                'registro': RegistroAsistenciaMaestroSerializer(registro).data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RegistroRetiroAlumnoViewSet(viewsets.ModelViewSet):
    queryset = RegistroRetiroAlumno.objects.all()
    serializer_class = RegistroRetiroAlumnoSerializer
    permission_classes = [IsMaestroOrDirectivo]

    def get_queryset(self):
        """Filtrar registros según el rol del usuario y parámetros"""
        queryset = self.queryset
        
        # Filtros por parámetros de query
        curso_id = self.request.query_params.get('curso', None)
        fecha = self.request.query_params.get('fecha', None)
        
        if curso_id:
            queryset = queryset.filter(curso_id=curso_id)
        if fecha:
            queryset = queryset.filter(fecha=fecha)
        
        # Filtrar por permisos
        if self.request.user.es_directivo:
            return queryset.select_related('alumno', 'familiar', 'maestro', 'curso')
        elif self.request.user.es_maestro:
            # Los maestros solo ven retiros de alumnos de sus cursos
            return queryset.filter(curso__maestros=self.request.user).select_related('alumno', 'familiar', 'maestro', 'curso')
        return queryset.none()

    def perform_create(self, serializer):
        # Asegurar que se asigne el curso del alumno
        alumno = serializer.validated_data['alumno']
        serializer.save(curso=alumno.curso)
class AvisoDirectivoViewSet(viewsets.ModelViewSet):
    queryset = AvisoDirectivo.objects.all()
    serializer_class = AvisoDirectivoSerializer
    permission_classes = [IsDirectivo]

    @action(detail=False, methods=['get'])
    def pendientes(self, request):  # Added 'request' parameter
        """Obtener avisos pendientes de procesar"""
        avisos = self.queryset.filter(procesado=False).select_related('maestro', 'curso')
        data = []
        for aviso in avisos:
            data.append({
                'id': aviso.id,
                'tipo': aviso.tipo,
                'maestro_nombre': f"{aviso.maestro.first_name} {aviso.maestro.last_name}",
                'curso_nombre': aviso.curso.nombre,
                'fecha': aviso.fecha,
                'hora_solicitada': aviso.hora_solicitada.strftime('%H:%M')  # MOSTRAR LA HORA GUARDADA
            })
        return Response(data)

    @action(detail=True, methods=['post'])
    def procesar(self, request, pk=None):
        """Procesar aviso automáticamente usando la hora guardada"""
        try:
            aviso = self.get_object()
            
            if aviso.procesado:
                return Response(
                    {'error': 'Este aviso ya fue procesado'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Usar la hora que se guardó cuando el maestro envió el aviso
            hora_a_registrar = aviso.hora_solicitada

            if aviso.tipo == 'ingreso':
                # Registrar ingreso
                registro, created = RegistroAsistenciaMaestro.objects.get_or_create(
                    maestro=aviso.maestro,
                    curso=aviso.curso,
                    fecha=aviso.fecha,
                    defaults={'hora_ingreso': hora_a_registrar}
                )
                
                if not created:
                    if registro.hora_ingreso:
                        return Response(
                            {'error': 'Ya existe un registro de ingreso para este maestro y curso'}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    else:
                        registro.hora_ingreso = hora_a_registrar
                        registro.save()

            elif aviso.tipo == 'salida':
                # Registrar salida
                try:
                    registro = RegistroAsistenciaMaestro.objects.get(
                        maestro=aviso.maestro,
                        curso=aviso.curso,
                        fecha=aviso.fecha
                    )
                    
                    if not registro.hora_ingreso:
                        return Response(
                            {'error': 'No hay registro de ingreso para procesar la salida'}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    if registro.hora_salida:
                        return Response(
                            {'error': 'Ya existe un registro de salida para este maestro y curso'}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    registro.hora_salida = hora_a_registrar
                    registro.save()
                    
                except RegistroAsistenciaMaestro.DoesNotExist:
                    return Response(
                        {'error': 'No hay registro de ingreso para procesar la salida'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Marcar aviso como procesado
            aviso.procesado = True
            aviso.procesado_por = request.user
            aviso.fecha_procesado = timezone.now()
            aviso.save()

            return Response({
                'message': f'{aviso.tipo.capitalize()} procesado correctamente a las {hora_a_registrar.strftime("%H:%M")}'
            })

        except AvisoDirectivo.DoesNotExist:
            return Response(
                {'error': 'Aviso no encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )

class RegistroAsistenciaAlumnoViewSet(viewsets.ModelViewSet):
    queryset = RegistroAsistenciaAlumno.objects.all()
    serializer_class = RegistroAsistenciaAlumnoSerializer
    permission_classes = [IsMaestroOrDirectivo]

    def get_queryset(self):
        """Filtrar registros según el rol del usuario"""
        queryset = self.queryset
        
        # Filtros por parámetros de query
        curso_id = self.request.query_params.get('curso', None)
        fecha = self.request.query_params.get('fecha', None)
        
        if curso_id:
            queryset = queryset.filter(curso_id=curso_id)
        if fecha:
            queryset = queryset.filter(fecha=fecha)
        
        # Filtrar por permisos
        if self.request.user.es_directivo:
            return queryset
        elif self.request.user.es_maestro:
            # Los maestros solo ven asistencia de alumnos de sus cursos
            return queryset.filter(curso__maestros=self.request.user)
        return queryset.none()

    @action(detail=False, methods=['post'], permission_classes=[IsMaestroOrDirectivo])
    def registrar_masiva(self, request):
        """Registrar asistencia masiva para un curso en una fecha"""
        curso_id = request.data.get('curso')
        fecha = request.data.get('fecha')
        maestro_id = request.data.get('maestro')
        registros = request.data.get('registros', [])

        if not all([curso_id, fecha, maestro_id, registros]):
            return Response(
                {'error': 'Faltan campos requeridos: curso, fecha, maestro, registros'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            curso = Curso.objects.get(id=curso_id)
            maestro = CustomUser.objects.get(id=maestro_id, es_maestro=True)
            
            # Verificar que el maestro puede registrar asistencia para este curso
            if not request.user.es_directivo and not curso.maestros.filter(id=request.user.id).exists():
                return Response(
                    {'error': 'No tienes permisos para registrar asistencia en este curso'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            registros_creados = []
            registros_actualizados = []
            
            for registro_data in registros:
                alumno_id = registro_data.get('alumno')
                presente = registro_data.get('presente', False)
                hora_llegada = registro_data.get('hora_llegada')
                
                try:
                    alumno = Alumno.objects.get(id=alumno_id, curso=curso)
                    
                    # Crear o actualizar el registro
                    registro, created = RegistroAsistenciaAlumno.objects.update_or_create(
                        alumno=alumno,
                        fecha=fecha,
                        defaults={
                            'curso': curso,
                            'maestro': maestro,
                            'presente': presente,
                            'hora_llegada': hora_llegada if presente and hora_llegada else None
                        }
                    )
                    
                    if created:
                        registros_creados.append(registro.id)
                    else:
                        registros_actualizados.append(registro.id)
                        
                except Alumno.DoesNotExist:
                    return Response(
                        {'error': f'Alumno con ID {alumno_id} no encontrado en el curso'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            return Response({
                'message': 'Asistencia registrada correctamente',
                'registros_creados': len(registros_creados),
                'registros_actualizados': len(registros_actualizados),
                'total_procesados': len(registros_creados) + len(registros_actualizados)
            })
            
        except Curso.DoesNotExist:
            return Response({'error': 'Curso no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except CustomUser.DoesNotExist:
            return Response({'error': 'Maestro no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {'error': f'Error interno: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], permission_classes=[IsMaestroOrDirectivo])
    def marcar_ausencias_automaticas(self, request):
        """
        Marca automáticamente como ausentes a los alumnos sin registro
        después de que termine el horario de clases
        """
        serializer = MarcadoAusenciasSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        curso_id = serializer.validated_data.get('curso')
        fecha = serializer.validated_data.get('fecha', timezone.now().date())
        
        try:
            if curso_id:
                # Marcar ausencias para un curso específico
                curso = Curso.objects.get(id=curso_id)
                
                # Verificar permisos
                if not request.user.es_directivo and not curso.maestros.filter(id=request.user.id).exists():
                    return Response(
                        {'error': 'No tienes permisos para marcar ausencias en este curso'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                ausencias_marcadas, mensaje = curso.marcar_ausencias_automaticas(fecha, request.user)
                
                return Response({
                    'success': True,
                    'message': mensaje,
                    'curso': curso.nombre,
                    'fecha': fecha.strftime('%Y-%m-%d'),
                    'ausencias_marcadas': ausencias_marcadas
                }, status=status.HTTP_200_OK)
                
            else:
                # Marcar ausencias para todos los cursos del usuario
                resultado = Curso.marcar_ausencias_masivas(fecha, request.user)
                
                if resultado['success']:
                    return Response(resultado, status=status.HTTP_200_OK)
                else:
                    return Response(resultado, status=status.HTTP_400_BAD_REQUEST)
                
        except Curso.DoesNotExist:
            return Response(
                {'error': 'Curso no encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Error interno: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], permission_classes=[IsMaestroOrDirectivo])
    def verificar_horarios_cursos(self, request):
        """
        Verifica qué cursos ya pasaron su horario de clases
        """
        fecha = timezone.now().date()
        
        # Obtener cursos según permisos
        if request.user.es_directivo:
            cursos = Curso.objects.all()
        elif request.user.es_maestro:
            cursos = Curso.objects.filter(maestros=request.user)
        else:
            cursos = Curso.objects.none()
        
        resultados = []
        for curso in cursos:
            hora_inicio, hora_fin = curso.parse_horario()
            ya_paso = curso.ya_paso_horario(fecha)
            alumnos_sin_registro = curso.get_alumnos_sin_asistencia(fecha).count()
            
            resultados.append({
                'curso_id': curso.id,
                'curso_nombre': curso.nombre,
                'horario': curso.horario,
                'hora_fin': hora_fin.strftime('%H:%M') if hora_fin else None,
                'ya_paso_horario': ya_paso,
                'alumnos_sin_registro': alumnos_sin_registro,
                'puede_marcar_ausencias': ya_paso and alumnos_sin_registro > 0
            })
        
        return Response({
            'fecha': fecha.strftime('%Y-%m-%d'),
            'cursos': resultados
        })

    @action(detail=False, methods=['get'], permission_classes=[IsMaestroOrDirectivo])
    def estadisticas_asistencia(self, request):
        """
        Obtiene estadísticas de asistencia
        """
        serializer = EstadisticasAsistenciaSerializer(data=request.query_params)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        fecha_inicio = serializer.validated_data.get('fecha_inicio')
        fecha_fin = serializer.validated_data.get('fecha_fin')
        curso_id = serializer.validated_data.get('curso')
        
        curso_obj = None
        if curso_id:
            try:
                curso_obj = Curso.objects.get(id=curso_id)
                # Verificar permisos
                if not request.user.es_directivo and not curso_obj.maestros.filter(id=request.user.id).exists():
                    return Response(
                        {'error': 'No tienes permisos para ver estadísticas de este curso'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Curso.DoesNotExist:
                return Response(
                    {'error': 'Curso no encontrado'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        estadisticas = RegistroAsistenciaAlumno.obtener_estadisticas_ausencias(
            fecha_inicio, fecha_fin, curso_obj
        )
        
        return Response({
            'periodo': {
                'fecha_inicio': fecha_inicio.strftime('%Y-%m-%d') if fecha_inicio else None,
                'fecha_fin': fecha_fin.strftime('%Y-%m-%d') if fecha_fin else None,
                'curso': curso_obj.nombre if curso_obj else 'Todos los cursos'
            },
            'estadisticas': estadisticas
        })

    @action(detail=False, methods=['post'], permission_classes=[IsDirectivo])
    def forzar_marcado_ausencias(self, request):
        """
        Permite a los directivos forzar el marcado de ausencias sin verificar horarios
        """
        serializer = MarcadoAusenciasSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        curso_id = serializer.validated_data.get('curso')
        fecha = serializer.validated_data.get('fecha', timezone.now().date())
        
        try:
            if curso_id:
                curso = Curso.objects.get(id=curso_id)
                
                # Forzar marcado sin verificar horario
                alumnos_sin_registro = curso.get_alumnos_sin_asistencia(fecha)
                maestro = curso.maestros.first()
                
                if not maestro:
                    return Response(
                        {'error': 'No hay maestros asignados a este curso'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if not alumnos_sin_registro.exists():
                    return Response({
                        'message': 'Todos los alumnos ya tienen registro de asistencia',
                        'ausencias_marcadas': 0
                    })
                
                # Crear registros de ausencia
                registros_crear = []
                for alumno in alumnos_sin_registro:
                    registros_crear.append(
                        RegistroAsistenciaAlumno(
                            alumno=alumno,
                            curso=curso,
                            maestro=maestro,
                            fecha=fecha,
                            presente=False,
                            hora_llegada=None
                        )
                    )
                
                RegistroAsistenciaAlumno.objects.bulk_create(registros_crear)
                
                return Response({
                    'success': True,
                    'message': f'Marcadas {len(registros_crear)} ausencias forzadamente',
                    'curso': curso.nombre,
                    'fecha': fecha.strftime('%Y-%m-%d'),
                    'ausencias_marcadas': len(registros_crear)
                })
            else:
                # Procesar todos los cursos
                resultado = Curso.marcar_ausencias_masivas(fecha, request.user)
                return Response(resultado)
                
        except Curso.DoesNotExist:
            return Response(
                {'error': 'Curso no encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Error interno: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class CuotaCursoViewSet(viewsets.ModelViewSet):
    queryset = CuotaCurso.objects.all()
    serializer_class = CuotaCursoSerializer
    permission_classes = [IsDirectivo]
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros opcionales
        curso_id = self.request.query_params.get('curso')
        año = self.request.query_params.get('año')
        mes = self.request.query_params.get('mes')
        vencidas = self.request.query_params.get('vencidas')
        
        if curso_id:
            queryset = queryset.filter(curso_id=curso_id)
        if año:
            queryset = queryset.filter(año=año)
        if mes:
            queryset = queryset.filter(mes=mes)
        if vencidas == 'true':
            queryset = queryset.filter(fecha_vencimiento__lt=timezone.now().date())
        
        return queryset
    @action(detail=False, methods=['post'], permission_classes=[IsDirectivo])
    def procesar_vencimientos(self, request):
        """
        Procesa todas las cuotas vencidas y marca deudores automáticamente
        """
        serializer = ProcesamientoVencimientosSerializer(data=request.data)
        
        if serializer.is_valid():
            fecha = serializer.validated_data.get('fecha', timezone.now().date())
        else:
            fecha = timezone.now().date()
        
        try:
            resultado = CuotaCurso.procesar_vencimientos_masivos(fecha)
            return Response(resultado, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'Error al procesar vencimientos: {str(e)}',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsDirectivo])
    def procesar_vencimiento_cuota(self, request, pk=None):
        """
        Procesa vencimiento para una cuota específica
        """
        cuota = self.get_object()
        
        try:
            deudores_marcados, mensaje = cuota.marcar_deudores_automaticamente()
            return Response({
                'success': True,
                'cuota_id': cuota.id,
                'cuota': str(cuota),
                'deudores_marcados': deudores_marcados,
                'mensaje': mensaje,
                'esta_vencida': cuota.esta_vencida,
                'dias_vencida': cuota.dias_vencida
            })
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'Error al procesar cuota: {str(e)}',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], permission_classes=[IsDirectivo])
    def cuotas_vencidas(self, request):
        """
        Obtiene todas las cuotas vencidas
        """
        fecha_actual = timezone.now().date()
        cuotas_vencidas = self.queryset.filter(
            fecha_vencimiento__lt=fecha_actual
        ).order_by('-fecha_vencimiento')
        
        # Agregar información de deudores a cada cuota
        resultado = []
        for cuota in cuotas_vencidas:
            cuota_data = self.get_serializer(cuota).data
            cuota_data['alumnos_deudores'] = cuota.get_alumnos_deudores().count()
            resultado.append(cuota_data)
        
        return Response({
            'total_cuotas_vencidas': len(resultado),
            'fecha_consulta': fecha_actual.strftime('%Y-%m-%d'),
            'cuotas': resultado
        })
    
    @action(detail=True, methods=['get'], permission_classes=[IsMaestroOrDirectivo])
    def deudores(self, request, pk=None):
        """
        Obtiene los alumnos deudores de una cuota específica
        """
        cuota = self.get_object()
        alumnos_deudores = cuota.get_alumnos_deudores()
        
        deudores_data = []
        for alumno in alumnos_deudores:
            # Buscar registro de deudor si existe
            try:
                deudor = DeudorCuota.objects.get(alumno=alumno, cuota=cuota)
                deudores_data.append({
                    'alumno_id': alumno.id,
                    'alumno_nombre': f"{alumno.nombre} {alumno.apellido}",
                    'tiene_registro_deudor': True,
                    'fecha_marcado': deudor.fecha_marcado_deudor,
                    'dias_atraso': deudor.dias_atraso_actual,
                    'monto_adeudado': deudor.monto_adeudado
                })
            except DeudorCuota.DoesNotExist:
                deudores_data.append({
                    'alumno_id': alumno.id,
                    'alumno_nombre': f"{alumno.nombre} {alumno.apellido}",
                    'tiene_registro_deudor': False,
                    'fecha_marcado': None,
                    'dias_atraso': cuota.dias_vencida if cuota.esta_vencida else 0,
                    'monto_adeudado': cuota.monto
                })
        
        return Response({
            'cuota': str(cuota),
            'fecha_vencimiento': cuota.fecha_vencimiento,
            'esta_vencida': cuota.esta_vencida,
            'dias_vencida': cuota.dias_vencida,
            'total_deudores': len(deudores_data),
            'deudores': deudores_data
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsMaestroOrDirectivo])
    def resumen_cuotas(self, request):
        """
        Obtiene un resumen general de las cuotas y sus estados
        """
        fecha_actual = timezone.now().date()
        
        # Estadísticas generales
        total_cuotas = self.queryset.count()
        cuotas_vencidas = self.queryset.filter(fecha_vencimiento__lt=fecha_actual).count()
        cuotas_vigentes = self.queryset.filter(fecha_vencimiento__gte=fecha_actual).count()
        
        # Cuotas por curso
        cuotas_por_curso = {}
        for cuota in self.queryset.select_related('curso'):
            curso_nombre = cuota.curso.nombre
            if curso_nombre not in cuotas_por_curso:
                cuotas_por_curso[curso_nombre] = {
                    'total': 0,
                    'vencidas': 0,
                    'vigentes': 0,
                    'total_deudores': 0
                }
            
            cuotas_por_curso[curso_nombre]['total'] += 1
            
            if cuota.esta_vencida:
                cuotas_por_curso[curso_nombre]['vencidas'] += 1
                cuotas_por_curso[curso_nombre]['total_deudores'] += cuota.get_alumnos_deudores().count()
            else:
                cuotas_por_curso[curso_nombre]['vigentes'] += 1
        
        return Response({
            'fecha_consulta': fecha_actual.strftime('%Y-%m-%d'),
            'resumen_general': {
                'total_cuotas': total_cuotas,
                'cuotas_vencidas': cuotas_vencidas,
                'cuotas_vigentes': cuotas_vigentes
            },
            'por_curso': cuotas_por_curso
        })
class DeudorCuotaViewSet(viewsets.ModelViewSet):
    queryset = DeudorCuota.objects.all()
    serializer_class = DeudorCuotaSerializer
    permission_classes = [IsMaestroOrDirectivo]
    
    def get_queryset(self):
        queryset = super().get_queryset()
         # Filtros opcionales
        curso_id = self.request.query_params.get('curso')
        año = self.request.query_params.get('año')
        mes = self.request.query_params.get('mes')
        solo_activos = self.request.query_params.get('solo_activos', 'true')
        
        if curso_id:
            queryset = queryset.filter(cuota__curso_id=curso_id)
        if año:
            queryset = queryset.filter(cuota__año=año)
        if mes:
            queryset = queryset.filter(cuota__mes=mes)
        if solo_activos == 'true':
            queryset = queryset.filter(pagado=False)
        
        # Filtros opcionales
        alumno_id = self.request.query_params.get('alumno', None)
        cuota_id = self.request.query_params.get('cuota', None)
        solo_pendientes = self.request.query_params.get('solo_pendientes', None)
        
        if alumno_id:
            queryset = queryset.filter(alumno_id=alumno_id)
        
        if cuota_id:
            queryset = queryset.filter(cuota_id=cuota_id)
        
        if solo_pendientes and solo_pendientes.lower() in ['true', '1']:
            queryset = queryset.filter(pagado=False)
        
        return queryset.select_related('alumno', 'cuota', 'cuota__curso')
    
    @action(detail=True, methods=['post'], permission_classes=[IsDirectivo])
    def marcar_pagado(self, request, pk=None):
        """
        Marca una deuda como pagada manualmente
        """
        deudor = self.get_object()
        
        if deudor.pagado:
            return Response(
                {'message': 'Esta deuda ya está marcada como pagada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            deudor.marcar_como_pagado()
            return Response({
                'message': 'Deuda marcada como pagada exitosamente',
                'deudor': self.get_serializer(deudor).data
            })
        except Exception as e:
            return Response(
                {'error': f'Error al marcar como pagado: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], permission_classes=[IsMaestroOrDirectivo])
    def por_alumno(self, request):
        """
        Obtiene todas las deudas agrupadas por alumno
        """
        solo_pendientes = request.query_params.get('solo_pendientes', 'true').lower() in ['true', '1']
        
        queryset = self.get_queryset()
        if solo_pendientes:
            queryset = queryset.filter(pagado=False)
        
        # Agrupar por alumno
        deudas_por_alumno = {}
        for deuda in queryset:
            alumno_key = deuda.alumno.id
            alumno_nombre = f"{deuda.alumno.nombre} {deuda.alumno.apellido}"
            
            if alumno_key not in deudas_por_alumno:
                deudas_por_alumno[alumno_key] = {
                    'alumno_id': alumno_key,
                    'alumno_nombre': alumno_nombre,
                    'total_deudas': 0,
                    'monto_total_adeudado': 0,
                    'deudas': []
                }
            
            deudas_por_alumno[alumno_key]['total_deudas'] += 1
            deudas_por_alumno[alumno_key]['monto_total_adeudado'] += float(deuda.monto_adeudado)
            deudas_por_alumno[alumno_key]['deudas'].append(
                self.get_serializer(deuda).data
            )
        
        return Response({
            'solo_pendientes': solo_pendientes,
            'total_alumnos_con_deudas': len(deudas_por_alumno),
            'alumnos': list(deudas_por_alumno.values())
        })

class PagoCuotaViewSet(viewsets.ModelViewSet):
    queryset = PagoCuota.objects.all()
    serializer_class = PagoCuotaSerializer
    permission_classes = [IsMaestroOrDirectivo]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros opcionales
        alumno_id = self.request.query_params.get('alumno', None)
        cuota_id = self.request.query_params.get('cuota', None)
        estado_pago = self.request.query_params.get('estado', None)
        fecha_desde = self.request.query_params.get('fecha_desde', None)
        fecha_hasta = self.request.query_params.get('fecha_hasta', None)
        
        if alumno_id:
            queryset = queryset.filter(alumno_id=alumno_id)
        
        if cuota_id:
            queryset = queryset.filter(cuota_id=cuota_id)
        
        if estado_pago:
            queryset = queryset.filter(estado_pago=estado_pago)
        
        if fecha_desde:
            try:
                fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha_pago__gte=fecha_desde)
            except ValueError:
                pass
        
        if fecha_hasta:
            try:
                fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha_pago__lte=fecha_hasta)
            except ValueError:
                pass
        
        return queryset.select_related('alumno', 'cuota', 'cuota__curso', 'familiar')
    
    @action(detail=False, methods=['get'], permission_classes=[IsMaestroOrDirectivo])
    def estadisticas_pagos(self, request):
        """
        Obtiene estadísticas de los pagos realizados
        """
        queryset = self.get_queryset()
        
        total_pagos = queryset.count()
        pagos_a_tiempo = queryset.filter(estado_pago='a_tiempo').count()
        pagos_con_atraso = queryset.filter(estado_pago='con_atraso').count()
        
        # Monto total recaudado
        monto_total = sum(float(pago.monto_pagado) for pago in queryset)
        
        # Pagos por mes
        pagos_por_mes = {}
        for pago in queryset:
            mes_key = pago.fecha_pago.strftime('%Y-%m')
            if mes_key not in pagos_por_mes:
                pagos_por_mes[mes_key] = {
                    'cantidad': 0,
                    'monto_total': 0,
                    'a_tiempo': 0,
                    'con_atraso': 0
                }
            
            pagos_por_mes[mes_key]['cantidad'] += 1
            pagos_por_mes[mes_key]['monto_total'] += float(pago.monto_pagado)
            
            if pago.estado_pago == 'a_tiempo':
                pagos_por_mes[mes_key]['a_tiempo'] += 1
            else:
                pagos_por_mes[mes_key]['con_atraso'] += 1
        
        return Response({
            'resumen_general': {
                'total_pagos': total_pagos,
                'pagos_a_tiempo': pagos_a_tiempo,
                'pagos_con_atraso': pagos_con_atraso,
                'porcentaje_a_tiempo': round((pagos_a_tiempo / total_pagos * 100) if total_pagos > 0 else 0, 2),
                'monto_total_recaudado': monto_total
            },
            'por_mes': pagos_por_mes
        })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def me_view(request):
    """Vista para obtener información del usuario actual"""
    return Response({
        'id': request.user.id,
        'username': request.user.username,
        'email': request.user.email,
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'es_maestro': request.user.es_maestro,
        'es_directivo': request.user.es_directivo,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    """Enviar token de recuperación de contraseña"""
    serializer = ForgotPasswordSerializer(data=request.data)
    
    if serializer.is_valid():
        email = serializer.validated_data['email']
        
        try:
            user = CustomUser.objects.get(email=email)
            
            # Invalidar tokens anteriores
            PasswordResetToken.objects.filter(user=user, used=False).update(used=True)
            
            # Crear nuevo token
            token = generate_random_token()
            reset_token = PasswordResetToken.objects.create(
                user=user,
                token=token
            )
            
            # Enviar email
            subject = 'Recuperación de Contraseña - Sistema Escolar'
            message = f"""
Hola {user.first_name},

Has solicitado recuperar tu contraseña. Utiliza el siguiente código para crear una nueva contraseña:

Código de recuperación: {token}

Este código expira en 24 horas.

Si no solicitaste esta recuperación, puedes ignorar este mensaje.

Saludos,
Sistema de Gestión Escolar
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
            return Response({
                'message': 'Se ha enviado un código de recuperación a tu correo electrónico'
            })
            
        except CustomUser.DoesNotExist:
            # Por seguridad, no revelamos si el email existe o no
            return Response({
                'message': 'Si el correo existe en nuestro sistema, recibirás las instrucciones de recuperación'
            })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_username(request):
    """Enviar recordatorio de nombre de usuario"""
    serializer = ForgotUsernameSerializer(data=request.data)
    
    if serializer.is_valid():
        email = serializer.validated_data['email']
        
        try:
            user = CustomUser.objects.get(email=email)
            
            # Enviar email con el nombre de usuario
            subject = 'Recuperación de Usuario - Sistema Escolar'
            message = f"""
Hola {user.first_name},

Has solicitado recordar tu nombre de usuario.

Tu nombre de usuario es: {user.username}

Si no solicitaste esta información, puedes ignorar este mensaje.

Saludos,
Sistema de Gestión Escolar
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
            return Response({
                'message': 'Se ha enviado tu nombre de usuario a tu correo electrónico'
            })
            
        except CustomUser.DoesNotExist:
            # Por seguridad, no revelamos si el email existe o no
            return Response({
                'message': 'Si el correo existe en nuestro sistema, recibirás tu nombre de usuario'
            })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """Cambiar contraseña usando token"""
    serializer = ResetPasswordSerializer(data=request.data)
    
    if serializer.is_valid():
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        try:
            reset_token = PasswordResetToken.objects.get(
                token=token,
                used=False
            )
            
            if reset_token.is_expired():
                return Response({
                    'error': 'El token ha expirado. Solicita un nuevo código de recuperación.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Cambiar la contraseña
            user = reset_token.user
            user.set_password(new_password)
            user.save()
            
            # Marcar token como usado
            reset_token.used = True
            reset_token.save()
            
            return Response({
                'message': 'Contraseña cambiada exitosamente. Ya puedes iniciar sesión con tu nueva contraseña.'
            })
            
        except PasswordResetToken.DoesNotExist:
            return Response({
                'error': 'Token inválido o ya utilizado'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_reset_token(request):
    """Verificar si un token de recuperación es válido"""
    token = request.data.get('token')
    
    if not token:
        return Response({
            'error': 'Token requerido'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        reset_token = PasswordResetToken.objects.get(
            token=token,
            used=False
        )
        
        if reset_token.is_expired():
            return Response({
                'valid': False,
                'error': 'Token expirado'
            })
        
        return Response({
            'valid': True,
            'username': reset_token.user.username
        })
        
    except PasswordResetToken.DoesNotExist:
        return Response({
            'valid': False,
            'error': 'Token inválido'
        })
    
@permission_classes([IsDirectivo])
def ejecutar_recordatorios(request):
    """
    Endpoint para ejecutar recordatorios manualmente
    """
    tipo_recordatorio = request.data.get('tipo', 'inicio_mes')
    fecha_especifica = request.data.get('fecha', None)
    
    if tipo_recordatorio not in ['inicio_mes', 'vencimiento']:
        return Response(
            {'error': 'Tipo de recordatorio inválido. Use: inicio_mes o vencimiento'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Capturar la salida del comando
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        # Ejecutar el comando
        if fecha_especifica:
            call_command('enviar_recordatorios', '--tipo', tipo_recordatorio, '--fecha', fecha_especifica)
        else:
            call_command('enviar_recordatorios', '--tipo', tipo_recordatorio)
        
        # Restaurar stdout
        sys.stdout = old_stdout
        output = captured_output.getvalue()
        
        return Response({
            'success': True,
            'message': 'Recordatorios ejecutados exitosamente',
            'output': output,
            'tipo': tipo_recordatorio,
            'fecha': fecha_especifica
        })
        
    except Exception as e:
        sys.stdout = old_stdout
        return Response(
            {
                'success': False,
                'error': f'Error al ejecutar recordatorios: {str(e)}'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )