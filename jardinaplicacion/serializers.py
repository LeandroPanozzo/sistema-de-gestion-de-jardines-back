from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import (
    CustomUser, CicloLectivo, Curso, Alumno, Familiar,
    RegistroAsistenciaMaestro, RegistroRetiroAlumno, CuotaCurso, PagoCuota,
    ConfiguracionSistema, RegistroAsistenciaAlumno, AvisoDirectivo, DeudorCuota
)


class ConfiguracionSistemaSerializer(serializers.ModelSerializer):
    actualizado_por_nombre = serializers.SerializerMethodField()
    
    class Meta:
        model = ConfiguracionSistema
        fields = [
            'id', 'registro_asistencia_habilitado', 'fecha_actualizacion',
            'actualizado_por', 'actualizado_por_nombre'
        ]
        read_only_fields = ['fecha_actualizacion', 'actualizado_por']
    
    def get_actualizado_por_nombre(self, obj):
        if obj.actualizado_por:
            return f"{obj.actualizado_por.first_name} {obj.actualizado_por.last_name}"
        return None


class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'dni', 'telefono', 'direccion', 'fecha_nacimiento',
            'es_maestro', 'es_directivo', 'password'
        ]
        extra_kwargs = {
            'password': {'write_only': True}
        }
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        user = CustomUser.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user

class AvisarDirectivoSerializer(serializers.Serializer):
    curso_id = serializers.IntegerField()

    def validate_curso_id(self, value):
        try:
            curso = Curso.objects.get(id=value)
            if not curso.maestros.filter(id=self.context['request'].user.id).exists():
                raise serializers.ValidationError("No estás asignado a este curso")
            return value
        except Curso.DoesNotExist:
            raise serializers.ValidationError("El curso no existe")
class AvisoDirectivoSerializer(serializers.ModelSerializer):
    maestro_nombre = serializers.SerializerMethodField()
    curso_nombre = serializers.SerializerMethodField()
    procesado_por_nombre = serializers.SerializerMethodField()
    
    class Meta:
        model = AvisoDirectivo
        fields = [
            'id', 'maestro', 'maestro_nombre', 'curso', 'curso_nombre', 
            'fecha', 'tipo', 'procesado', 'procesado_por', 'procesado_por_nombre',
            'fecha_procesado'
        ]
        read_only_fields = ['procesado', 'procesado_por', 'fecha_procesado']
    
    def get_maestro_nombre(self, obj):
        return f"{obj.maestro.first_name} {obj.maestro.last_name}"
    
    def get_curso_nombre(self, obj):
        return obj.curso.nombre
    
    def get_procesado_por_nombre(self, obj):
        if obj.procesado_por:
            return f"{obj.procesado_por.first_name} {obj.procesado_por.last_name}"
        return None


class ProcesarAvisoSerializer(serializers.Serializer):
    """Serializer para procesar avisos de directivos"""
    hora = serializers.TimeField()
    
    def validate_hora(self, value):
        if not value:
            raise serializers.ValidationError("La hora es requerida")
        return value
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    
    def validate(self, data):
        username = data.get('username')
        password = data.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError('Credenciales inválidas')
            if not user.is_active:
                raise serializers.ValidationError('Usuario inactivo')
            data['user'] = user
        else:
            raise serializers.ValidationError('Debe proporcionar username y password')
        
        return data


class CicloLectivoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CicloLectivo
        fields = '__all__'


class CursoSerializer(serializers.ModelSerializer):
    maestros_nombres = serializers.SerializerMethodField()
    alumnos_inscriptos = serializers.ReadOnlyField()
    cupos_disponibles = serializers.ReadOnlyField()
    cuota_mensual_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = Curso
        fields = [
            'id', 'nombre', 'cupo_habilitado', 'turno', 'horario',
            'edad_sala', 'ciclo_lectivo', 'maestros', 'maestros_nombres',
            'alumnos_inscriptos', 'cupos_disponibles', 'cuota_mensual',
            'cuota_mensual_formatted', 'dia_vencimiento_cuota'
        ]
    
    def get_maestros_nombres(self, obj):
        """Devuelve los nombres completos de los maestros asignados"""
        return [f"{maestro.first_name} {maestro.last_name}" for maestro in obj.maestros.all()]
    
    def get_cuota_mensual_formatted(self, obj):
        """Devuelve la cuota formateada como string con símbolo de peso"""
        return f"${obj.cuota_mensual:,.2f}"
        
# Otros serializers que pueden necesitar actualización:
from rest_framework import serializers
from datetime import datetime, time

class RegistrarIngresoSerializer(serializers.Serializer):
    curso_id = serializers.IntegerField()
    hora_ingreso = serializers.TimeField()
    
    def validate_curso_id(self, value):
        # Verificar que el curso existe y el maestro esté asignado a él
        try:
            curso = Curso.objects.get(id=value)
            # Verificar que el maestro esté asignado al curso
            if not curso.maestros.filter(id=self.context['request'].user.id).exists():
                raise serializers.ValidationError("No estás asignado a este curso")
            return value
        except Curso.DoesNotExist:
            raise serializers.ValidationError("El curso no existe")
import logging

logger = logging.getLogger(__name__)
class RegistrarSalidaSerializer(serializers.Serializer):
    curso_id = serializers.IntegerField()
    hora_salida = serializers.TimeField()
    
    def validate(self, data):
        """Custom validation to ensure all required fields are present"""
        logger.info(f"Validating data: {data}")
        
        if 'curso_id' not in data:
            raise serializers.ValidationError("El campo curso_id es requerido")
        
        if 'hora_salida' not in data:
            raise serializers.ValidationError("El campo hora_salida es requerido")
            
        return data
    
    def validate_curso_id(self, value):
        """Verificar que el curso existe y el maestro esté asignado a él"""
        logger.info(f"Validating curso_id: {value}")
        
        try:
            curso = Curso.objects.get(id=value)
            # Verificar que el maestro esté asignado al curso
            if not curso.maestros.filter(id=self.context['request'].user.id).exists():
                raise serializers.ValidationError("No estás asignado a este curso")
            return value
        except Curso.DoesNotExist:
            raise serializers.ValidationError("El curso no existe")
    
    def validate_hora_salida(self, value):
        """Validar que la hora de salida sea válida"""
        logger.info(f"Validating hora_salida: {value}")
        
        if not value:
            raise serializers.ValidationError("La hora de salida es requerida")
            
        return value
# También vamos a mejorar el serializer principal
class RegistroAsistenciaMaestroSerializer(serializers.ModelSerializer):
    maestro_nombre = serializers.SerializerMethodField()
    curso_nombre = serializers.SerializerMethodField()
    curso_horario = serializers.SerializerMethodField()
    estado_asistencia = serializers.ReadOnlyField()
    
    class Meta:
        model = RegistroAsistenciaMaestro
        fields = [
            'id', 'maestro', 'maestro_nombre', 'curso', 'curso_nombre', 
            'curso_horario', 'fecha', 'hora_ingreso', 'hora_salida', 
            'ausente', 'estado_asistencia'
        ]
        read_only_fields = ['maestro', 'fecha', 'ausente']
    
    def get_maestro_nombre(self, obj):
        return f"{obj.maestro.first_name} {obj.maestro.last_name}"
    
    def get_curso_nombre(self, obj):
        return obj.curso.nombre
    
    def get_curso_horario(self, obj):
        return obj.curso.horario

class MarcarAusenteSerializer(serializers.Serializer):
    maestro_id = serializers.IntegerField()
    curso_id = serializers.IntegerField()
    
    def validate_maestro_id(self, value):
        """Verificar que el maestro existe y es maestro"""
        try:
            maestro = CustomUser.objects.get(id=value)
            if not maestro.es_maestro:
                raise serializers.ValidationError("El usuario no es un maestro")
            return value
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("El maestro no existe")
    
    def validate_curso_id(self, value):
        """Verificar que el curso existe"""
        try:
            Curso.objects.get(id=value)
            return value
        except Curso.DoesNotExist:
            raise serializers.ValidationError("El curso no existe")
class ProcesarAusenciasMasivasSerializer(serializers.Serializer):
    fecha = serializers.DateField(required=False)
    
    def validate_fecha(self, value):
        if value and value.weekday() >= 5:
            raise serializers.ValidationError("No se pueden procesar ausencias en fines de semana")
        return value
class HabilitarUsuarioSerializer(serializers.Serializer):
    es_maestro = serializers.BooleanField(required=False)
    es_directivo = serializers.BooleanField(required=False)

# En serializers.py - Alternativa con referencia de cadena

class AlumnoSerializer(serializers.ModelSerializer):
    edad = serializers.ReadOnlyField()
    curso_nombre = serializers.SerializerMethodField()
    familiares = serializers.SerializerMethodField()  # Usar SerializerMethodField
    
    class Meta:
        model = Alumno
        fields = [
            'id', 'nombre', 'apellido', 'dni', 'fecha_nacimiento',
            'curso', 'curso_nombre', 'edad', 'familiares'
        ]
    
    def get_curso_nombre(self, obj):
        return obj.curso.nombre if obj.curso else None
    
    def get_familiares(self, obj):
        # Usar el serializer que se define después
        from .serializers import FamiliarSerializer  # Import local
        return FamiliarSerializer(obj.familiares.all(), many=True).data
    
    def validate(self, data):
        curso = data.get('curso')
        if curso and curso.cupos_disponibles <= 0:
            if self.instance and self.instance.curso == curso:
                return data
            raise serializers.ValidationError('No hay cupos disponibles en este curso')
        return data


class FamiliarSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.SerializerMethodField()
    
    class Meta:
        model = Familiar
        fields = [
            'id', 'nombre', 'apellido', 'dni', 'telefono', 'direccion',
            'mail', 'relacion_con_alumno', 'alumno', 'alumno_nombre'
        ]
    
    def get_alumno_nombre(self, obj):
        return f"{obj.alumno.nombre} {obj.alumno.apellido}"
class MarcadoAusenciasSerializer(serializers.Serializer):
    """Serializer para el marcado de ausencias automáticas"""
    curso = serializers.IntegerField(required=False, help_text="ID del curso específico (opcional)")
    fecha = serializers.DateField(
        required=False, 
        help_text="Fecha para marcar ausencias (opcional, por defecto hoy)"
    )
    
    def validate_fecha(self, value):
        """Validar que la fecha no sea futura"""
        if value and value > timezone.now().date():
            raise serializers.ValidationError("No se pueden marcar ausencias para fechas futuras")
        return value
    
    def validate(self, data):
        """Validaciones adicionales"""
        fecha = data.get('fecha', timezone.now().date())
        
        # Verificar que no sea fin de semana
        if fecha.weekday() >= 5:
            raise serializers.ValidationError("No se pueden marcar ausencias en fines de semana")
        
        return data
class EstadisticasAsistenciaSerializer(serializers.Serializer):
    """Serializer para obtener estadísticas de asistencia"""
    fecha_inicio = serializers.DateField(required=False)
    fecha_fin = serializers.DateField(required=False)
    curso = serializers.IntegerField(required=False)
    
    def validate(self, data):
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        
        if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
            raise serializers.ValidationError("La fecha de inicio no puede ser mayor a la fecha de fin")
        
        return data

class ResultadoAusenciasSerializer(serializers.Serializer):
    """Serializer para mostrar resultados del marcado de ausencias"""
    success = serializers.BooleanField()
    message = serializers.CharField()
    total_ausencias = serializers.IntegerField()
    cursos_procesados = serializers.IntegerField()
    fecha = serializers.CharField()
    resultados = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )


class RegistroRetiroAlumnoSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.SerializerMethodField()
    familiar_nombre = serializers.SerializerMethodField()
    maestro_nombre = serializers.SerializerMethodField()
    
    class Meta:
        model = RegistroRetiroAlumno
        fields = [
            'id', 'alumno', 'alumno_nombre', 'familiar', 'familiar_nombre',
            'maestro', 'maestro_nombre', 'fecha', 'hora_retiro'
        ]
    
    def get_alumno_nombre(self, obj):
        return f"{obj.alumno.nombre} {obj.alumno.apellido}"
    
    def get_familiar_nombre(self, obj):
        return f"{obj.familiar.nombre} {obj.familiar.apellido}"
    
    def get_maestro_nombre(self, obj):
        return f"{obj.maestro.first_name} {obj.maestro.last_name}"
    
    def get_alumno(self, obj):
        return {
            'id': obj.alumno.id,
            'nombre': obj.alumno.nombre,
            'apellido': obj.alumno.apellido,
            'dni': obj.alumno.dni
        }
    
    def get_familiar(self, obj):
        return {
            'id': obj.familiar.id,
            'nombre': obj.familiar.nombre,
            'apellido': obj.familiar.apellido,
            'relacion_con_alumno': obj.familiar.relacion_con_alumno
        }
    
    def get_maestro(self, obj):
        return {
            'id': obj.maestro.id,
            'first_name': obj.maestro.first_name,
            'last_name': obj.maestro.last_name
        }
    
    def validate(self, data):
        alumno = data.get('alumno')
        familiar = data.get('familiar')
        
        if familiar and familiar.alumno != alumno:
            raise serializers.ValidationError(
                'El familiar no está autorizado para retirar a este alumno'
            )
        
        return data

class RegistroAsistenciaAlumnoSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.SerializerMethodField()
    curso_nombre = serializers.SerializerMethodField()
    maestro_nombre = serializers.SerializerMethodField()

    class Meta:
        model = RegistroAsistenciaAlumno
        fields = [
            'id', 'alumno', 'alumno_nombre', 'curso', 'curso_nombre',
            'maestro', 'maestro_nombre', 'fecha', 'presente', 'hora_llegada'
        ]

    def get_alumno(self, obj):
        return {
            'id': obj.alumno.id,
            'nombre': obj.alumno.nombre,
            'apellido': obj.alumno.apellido,
            'dni': obj.alumno.dni,
            'edad': obj.alumno.edad
        }
    def get_maestro(self, obj):
        return {
            'id': obj.maestro.id,
            'first_name': obj.maestro.first_name,
            'last_name': obj.maestro.last_name
        }

    def get_alumno_nombre(self, obj):
        return f"{obj.alumno.nombre} {obj.alumno.apellido}"

    def get_curso_nombre(self, obj):
        return obj.curso.nombre

    def get_maestro_nombre(self, obj):
        return f"{obj.maestro.first_name} {obj.maestro.last_name}"

    def validate(self, data):
        alumno = data.get('alumno')
        curso = data.get('curso')
        
        # Validar que el alumno pertenece al curso
        if alumno and curso and alumno.curso != curso:
            raise serializers.ValidationError('El alumno no pertenece a este curso')
        
        return data

class CuotaCursoSerializer(serializers.ModelSerializer):
    curso_nombre = serializers.SerializerMethodField()
    mes_nombre = serializers.SerializerMethodField()
    esta_vencida = serializers.ReadOnlyField()
    dias_vencida = serializers.ReadOnlyField()
    total_deudores = serializers.SerializerMethodField()
    total_pagos = serializers.SerializerMethodField()
    
    class Meta:
        model = CuotaCurso
        fields = [
            'id', 'curso', 'curso_nombre', 'mes', 'mes_nombre',
            'año', 'monto', 'fecha_vencimiento', 'esta_vencida',
            'dias_vencida', 'total_deudores', 'total_pagos'
        ]
    
    def get_curso_nombre(self, obj):
        return obj.curso.nombre
    
    def get_mes_nombre(self, obj):
        meses = [
            '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]
        return meses[obj.mes]
    
    def get_total_deudores(self, obj):
        return obj.get_alumnos_deudores().count()
    
    def get_total_pagos(self, obj):
        return obj.pagos.count()

class DeudorCuotaSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.SerializerMethodField()
    cuota_detalle = serializers.SerializerMethodField()
    dias_atraso_actual = serializers.ReadOnlyField()
    
    class Meta:
        model = DeudorCuota
        fields = [
            'id', 'alumno', 'alumno_nombre', 'cuota', 'cuota_detalle',
            'fecha_vencimiento', 'fecha_marcado_deudor', 'dias_atraso',
            'dias_atraso_actual', 'monto_adeudado', 'pagado', 'fecha_pago'
        ]
    
    def get_alumno_nombre(self, obj):
        return f"{obj.alumno.nombre} {obj.alumno.apellido}"
    
    def get_cuota_detalle(self, obj):
        meses = [
            '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]
        return f"{meses[obj.cuota.mes]} {obj.cuota.año} - {obj.cuota.curso.nombre}"


class PagoCuotaSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.SerializerMethodField()
    familiar_nombre = serializers.SerializerMethodField()
    cuota_detalle = serializers.SerializerMethodField()
    descripcion_estado = serializers.ReadOnlyField()
    
    class Meta:
        model = PagoCuota
        fields = [
            'id', 'alumno', 'alumno_nombre', 'cuota', 'cuota_detalle',
            'familiar', 'familiar_nombre', 'fecha_pago', 'monto_pagado',
            'estado_pago', 'dias_atraso_pago', 'descripcion_estado'
        ]
    
    def get_alumno_nombre(self, obj):
        return f"{obj.alumno.nombre} {obj.alumno.apellido}"
    
    def get_familiar_nombre(self, obj):
        return f"{obj.familiar.nombre} {obj.familiar.apellido}"
    
    def get_cuota_detalle(self, obj):
        meses = [
            '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]
        return f"{meses[obj.cuota.mes]} {obj.cuota.año} - {obj.cuota.curso.nombre}"

class ProcesamientoVencimientosSerializer(serializers.Serializer):
    """Serializer para el endpoint de procesamiento de vencimientos"""
    fecha = serializers.DateField(required=False, help_text="Fecha para procesar vencimientos (por defecto: hoy)")


# Serializers específicos para operaciones comunes

class MaestroAsignacionSerializer(serializers.Serializer):
    maestro_id = serializers.IntegerField()
    accion = serializers.ChoiceField(choices=['asignar', 'desasignar'])
    
    def validate_maestro_id(self, value):
        """Validar que el maestro existe y es maestro habilitado"""
        try:
            maestro = CustomUser.objects.get(id=value, es_maestro=True)
            return value
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("El usuario no existe o no es maestro")
    
    def validate_accion(self, value):
        """Validar que la acción es válida"""
        if value not in ['asignar', 'desasignar']:
            raise serializers.ValidationError("Acción inválida. Debe ser 'asignar' o 'desasignar'")
        return value

class HabilitarUsuarioSerializer(serializers.Serializer):
    """Para habilitar usuarios como maestro/directivo"""
    usuario_id = serializers.IntegerField()
    es_maestro = serializers.BooleanField(required=False)
    es_directivo = serializers.BooleanField(required=False)

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("El correo electrónico es requerido")
        return value.lower()
class ForgotUsernameSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("El correo electrónico es requerido")
        return value.lower()

class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=100)
    new_password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)
    
    def validate_token(self, value):
        if not value:
            raise serializers.ValidationError("El código de recuperación es requerido")
        return value
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': "Las contraseñas no coinciden"
            })
        
        # Validaciones adicionales de contraseña
        password = data['new_password']
        
        if len(password) < 8:
            raise serializers.ValidationError({
                'new_password': "La contraseña debe tener al menos 8 caracteres"
            })
            
        if password.isdigit():
            raise serializers.ValidationError({
                'new_password': "La contraseña no puede ser solo números"
            })
            
        return data

class VerifyResetTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=100)