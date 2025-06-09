from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal


class ConfiguracionSistema(models.Model):
    """Configuración general del sistema"""
    registro_asistencia_habilitado = models.BooleanField(
        default=True,
        help_text="Permite a los maestros registrar su entrada y salida"
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(
        'CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'es_directivo': True},
        related_name='configuraciones_actualizadas'
    )
    
    class Meta:
        verbose_name = "Configuración del Sistema"
        verbose_name_plural = "Configuraciones del Sistema"
    
    def __str__(self):
        estado = "Habilitado" if self.registro_asistencia_habilitado else "Deshabilitado"
        return f"Registro de Asistencia: {estado}"
    
    @classmethod
    def get_configuracion(cls):
        """Obtener la configuración actual (crea una por defecto si no existe)"""
        config, created = cls.objects.get_or_create(
            pk=1,
            defaults={'registro_asistencia_habilitado': True}
        )
        return config


class CustomUser(AbstractUser):
    """Usuario personalizado que puede ser habilitado como maestro y/o directivo"""
    dni = models.CharField(max_length=10, unique=True)
    telefono = models.CharField(max_length=15, blank=True)
    direccion = models.TextField(blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    
    # Habilitaciones
    es_maestro = models.BooleanField(default=False)
    es_directivo = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"


class CicloLectivo(models.Model):
    """Ciclo lectivo anual"""
    inicio = models.DateField()
    finalizacion = models.DateField()
    
    class Meta:
        ordering = ['-inicio']
    
    def __str__(self):
        return f"Ciclo {self.inicio.year}"


class Curso(models.Model):
    """Cursos del jardín"""
    TURNOS = [
        ('mañana', 'Mañana'),
        ('intermedio', 'Intermedio'),
        ('tarde', 'Tarde'),
    ]
    EDADES_SALA = [
        (0, 'meses (0-11 meses)'),
        (1, '1 año'),
        (2, '2 años'),
        (3, '3 años'),
        (4, '4 años'),
        (5, '5 años'),
    ]

    nombre = models.CharField(max_length=100)
    cupo_habilitado = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    turno = models.CharField(max_length=10, choices=TURNOS)
    horario = models.CharField(max_length=100)  # Ej: "8:00 - 12:00"
    edad_sala = models.PositiveIntegerField(choices=EDADES_SALA)
    ciclo_lectivo = models.ForeignKey(CicloLectivo, on_delete=models.CASCADE, related_name='cursos')
    
    # NUEVO CAMPO: Cuota mensual del curso
    cuota_mensual = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Cuota mensual del curso en pesos",
        default=Decimal('0.00')
    )
     # NUEVO CAMPO: Día límite para pagar la cuota
    dia_vencimiento_cuota = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        default=10,
        help_text="Día del mes límite para pagar la cuota (máximo día 28 para evitar problemas con febrero)"
    )
    # Relación muchos a muchos con maestros
    maestros = models.ManyToManyField(
        CustomUser,
        limit_choices_to={'es_maestro': True},  # Esto ya incluye maestros+directivos
        related_name='cursos_asignados',
        blank=True
    )
    
    def get_maestros_disponibles(self):
        """Obtener todos los usuarios que pueden ser asignados como maestros"""
        return CustomUser.objects.filter(es_maestro=True)
    
    def puede_ser_maestro(self, usuario):
        """Verificar si un usuario puede ser asignado como maestro"""
        return usuario.es_maestro
    def get_fecha_vencimiento(self, mes, año):
        """
        Obtiene la fecha de vencimiento para un mes y año específicos
        """
        # Asegurar que el día no exceda los días del mes
        ultimo_dia_mes = calendar.monthrange(año, mes)[1]
        dia_vencimiento = min(self.dia_vencimiento_cuota, ultimo_dia_mes)
        
        return date(año, mes, dia_vencimiento)
        
    def __str__(self):
        return f"{self.nombre} - {self.turno} ({self.ciclo_lectivo})"
    
    @property
    def alumnos_inscriptos(self):
        return self.alumnos.count()
    
    @property
    def cupos_disponibles(self):
        return self.cupo_habilitado - self.alumnos_inscriptos
    
    def parse_horario(self):
        """
        Parsea el horario del curso para extraer hora de inicio y fin
        Formato esperado: "8:00 - 12:00" o "08:00-12:00"
        """
        try:
            # Limpiar espacios y normalizar formato
            horario_clean = re.sub(r'\s+', '', self.horario)
            
            # Buscar patrón de horario
            match = re.match(r'(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})', horario_clean)
            if match:
                hora_inicio = time(int(match.group(1)), int(match.group(2)))
                hora_fin = time(int(match.group(3)), int(match.group(4)))
                return hora_inicio, hora_fin
            
            return None, None
        except (ValueError, AttributeError):
            return None, None
    
    def ya_paso_horario(self, fecha=None, margen_minutos=30):
        """
        Verifica si ya pasó el horario de clases del curso
        """
        if fecha is None:
            fecha = timezone.now().date()
        
        # Solo verificar para el día actual
        if fecha != timezone.now().date():
            return True  # Para fechas pasadas, consideramos que ya pasó
        
        hora_inicio, hora_fin = self.parse_horario()
        if not hora_fin:
            return False
        
        hora_actual = timezone.now().time()
        hora_limite = (datetime.combine(fecha, hora_fin) + timedelta(minutes=margen_minutos)).time()
        
        return hora_actual >= hora_limite
    
    def get_alumnos_sin_asistencia(self, fecha):
        """
        Obtiene alumnos del curso que no tienen registro de asistencia en la fecha
        """
        return self.alumnos.exclude(
            registros_asistencia__fecha=fecha
        )
    
    def marcar_ausencias_automaticas(self, fecha, maestro=None):
        """
        Marca como ausentes a los alumnos sin registro de asistencia
        """
        # Verificar que no sea fin de semana
        if fecha.weekday() >= 5:  # Sábado (5) o Domingo (6)
            return 0, "No se procesan ausencias en fines de semana"
        
        # Verificar que ya pasó el horario (solo para fecha actual)
        if fecha == timezone.now().date() and not self.ya_paso_horario(fecha):
            return 0, "Aún no es hora de marcar ausencias para este curso"
        
        # Usar el primer maestro del curso si no se especifica uno
        if maestro is None:
            maestro = self.maestros.first()
        
        if not maestro:
            return 0, "No hay maestros asignados a este curso"
        
        # Obtener alumnos sin registro
        alumnos_sin_registro = self.get_alumnos_sin_asistencia(fecha)
        
        if not alumnos_sin_registro.exists():
            return 0, "Todos los alumnos ya tienen registro de asistencia"
        
        # Crear registros de ausencia usando bulk_create para mejor rendimiento
        registros_crear = []
        for alumno in alumnos_sin_registro:
            registros_crear.append(
                RegistroAsistenciaAlumno(
                    alumno=alumno,
                    curso=self,
                    maestro=maestro,
                    fecha=fecha,
                    presente=False,
                    hora_llegada=None
                )
            )
        
        RegistroAsistenciaAlumno.objects.bulk_create(registros_crear)
        
        return len(registros_crear), f"Marcadas {len(registros_crear)} ausencias automáticamente"
    def get_maestros_sin_asistencia(self, fecha):
        """
        Obtiene maestros del curso que no tienen registro de asistencia en la fecha
        """
        return self.maestros.exclude(
            registros_asistencia__fecha=fecha,
            registros_asistencia__curso=self
        )
    
    def marcar_ausencias_maestros_automaticas(self, fecha, margen_minutos=30):
        """
        Marca como ausentes a los maestros sin registro de asistencia
        """
        # Verificar que no sea fin de semana
        if fecha.weekday() >= 5:  # Sábado (5) o Domingo (6)
            return 0, "No se procesan ausencias en fines de semana"
        
        # Verificar que ya pasó el horario (solo para fecha actual)
        if fecha == timezone.now().date() and not self.ya_paso_horario(fecha, margen_minutos):
            return 0, "Aún no es hora de marcar ausencias para este curso"
        
        # Obtener maestros sin registro y sin avisos pendientes
        maestros_sin_registro = self.get_maestros_sin_asistencia(fecha)
        
        # Filtrar maestros que tampoco tienen avisos pendientes
        maestros_realmente_ausentes = []
        for maestro in maestros_sin_registro:
            # Verificar si tiene avisos pendientes para este curso y fecha
            tiene_aviso_pendiente = AvisoDirectivo.objects.filter(
                maestro=maestro,
                curso=self,
                fecha=fecha,
                procesado=False
            ).exists()
            
            if not tiene_aviso_pendiente:
                maestros_realmente_ausentes.append(maestro)
        
        if not maestros_realmente_ausentes:
            return 0, "Todos los maestros tienen registro de asistencia o avisos pendientes"
        
        # Crear registros de ausencia usando bulk_create para mejor rendimiento
        registros_crear = []
        for maestro in maestros_realmente_ausentes:
            registros_crear.append(
                RegistroAsistenciaMaestro(
                    maestro=maestro,
                    curso=self,
                    fecha=fecha,
                    hora_ingreso=None,
                    hora_salida=None,
                    ausente=True  # Nuevo campo para marcar ausencia
                )
            )
        
        RegistroAsistenciaMaestro.objects.bulk_create(registros_crear)
        
        return len(registros_crear), f"Marcadas {len(registros_crear)} ausencias de maestros automáticamente"

    @classmethod
    def marcar_ausencias_maestros_masivas(cls, fecha=None):
        """
        Marca ausencias de maestros para todos los cursos
        """
        if fecha is None:
            fecha = timezone.now().date()
        
        # Verificar que no sea fin de semana
        if fecha.weekday() >= 5:
            return {
                'success': False,
                'message': 'No se procesan ausencias en fines de semana',
                'total_ausencias': 0,
                'cursos_procesados': 0
            }
        
        cursos = cls.objects.all()
        total_ausencias = 0
        cursos_procesados = 0
        resultados = []
        
        for curso in cursos:
            ausencias_marcadas, mensaje = curso.marcar_ausencias_maestros_automaticas(fecha)
            
            if ausencias_marcadas > 0:
                total_ausencias += ausencias_marcadas
                cursos_procesados += 1
            
            resultados.append({
                'curso': curso.nombre,
                'ausencias_marcadas': ausencias_marcadas,
                'mensaje': mensaje
            })
        
        return {
            'success': True,
            'message': f'Proceso completado: {cursos_procesados} cursos procesados, {total_ausencias} ausencias de maestros marcadas',
            'total_ausencias': total_ausencias,
            'cursos_procesados': cursos_procesados,
            'resultados': resultados,
            'fecha': fecha.strftime('%Y-%m-%d')
        }


    @classmethod
    def marcar_ausencias_masivas(cls, fecha=None, maestro_usuario=None):
        """
        Marca ausencias para todos los cursos según el rol del usuario
        """
        if fecha is None:
            fecha = timezone.now().date()
        
        # Verificar que no sea fin de semana
        if fecha.weekday() >= 5:
            return {
                'success': False,
                'message': 'No se procesan ausencias en fines de semana',
                'total_ausencias': 0,
                'cursos_procesados': 0
            }
        
        # Obtener cursos según el rol del usuario
        if maestro_usuario and maestro_usuario.es_directivo:
            cursos = cls.objects.all()
        elif maestro_usuario and maestro_usuario.es_maestro:
            cursos = cls.objects.filter(maestros=maestro_usuario)
        else:
            cursos = cls.objects.none()
        
        total_ausencias = 0
        cursos_procesados = 0
        resultados = []
        
        for curso in cursos:
            ausencias_marcadas, mensaje = curso.marcar_ausencias_automaticas(fecha)
            
            if ausencias_marcadas > 0:
                total_ausencias += ausencias_marcadas
                cursos_procesados += 1
            
            resultados.append({
                'curso': curso.nombre,
                'ausencias_marcadas': ausencias_marcadas,
                'mensaje': mensaje
            })
        
        return {
            'success': True,
            'message': f'Proceso completado: {cursos_procesados} cursos procesados, {total_ausencias} ausencias marcadas',
            'total_ausencias': total_ausencias,
            'cursos_procesados': cursos_procesados,
            'resultados': resultados,
            'fecha': fecha.strftime('%Y-%m-%d')
        }



class Alumno(models.Model):
    """Alumnos del jardín"""
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=10, unique=True)
    fecha_nacimiento = models.DateField()
    
    # Relación con el curso
    curso = models.ForeignKey(
        Curso, 
        on_delete=models.CASCADE, 
        related_name='alumnos',
        null=True, blank=True
    )
    
    def __str__(self):
        return f"{self.nombre} {self.apellido}"
    
    @property
    def edad(self):
        from datetime import date
        today = date.today()
        return today.year - self.fecha_nacimiento.year - (
            (today.month, today.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )


class Familiar(models.Model):
    """Familiares autorizados a retirar alumnos"""
    RELACIONES = [
        ('padre', 'Padre'),
        ('madre', 'Madre'),
        ('abuelo', 'Abuelo'),
        ('abuela', 'Abuela'),
        ('ti@', 'Ti@'),
        ('herman@', 'herman@'),
        ('otro', 'Otro'),
    ]
    
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=10)
    telefono = models.CharField(max_length=15)
    direccion = models.TextField(blank=True)
    mail = models.EmailField(blank=True)
    
    # Relación con el alumno
    relacion_con_alumno = models.CharField(max_length=10, choices=RELACIONES)
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='familiares')
    
    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.relacion_con_alumno} de {self.alumno})"

class AvisoDirectivo(models.Model):
    """Avisos de maestros a directivos para registro de asistencia"""
    TIPO_CHOICES = [
        ('ingreso', 'Ingreso'),
        ('salida', 'Salida'),
    ]

    maestro = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        limit_choices_to={'es_maestro': True},
        related_name='avisos_enviados'
    )
    curso = models.ForeignKey(
        'Curso',
        on_delete=models.CASCADE,
        related_name='avisos_directivo'
    )
    fecha = models.DateField(default=timezone.now)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    hora_solicitada = models.TimeField()  # NUEVO CAMPO para almacenar la hora cuando se envía el aviso
    procesado = models.BooleanField(default=False)
    procesado_por = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'es_directivo': True},
        related_name='avisos_procesados'
    )
    fecha_procesado = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['maestro', 'curso', 'fecha', 'tipo']
        ordering = ['-fecha', 'curso__nombre']

    def __str__(self):
        return f"Aviso {self.tipo} - {self.maestro} - {self.curso.nombre} - {self.fecha} - {self.hora_solicitada}"
class RegistroAsistenciaMaestro(models.Model):
    """Registro de entrada y salida de maestros por curso"""
    maestro = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE,
        limit_choices_to={'es_maestro': True},
        related_name='registros_asistencia'
    )
    curso = models.ForeignKey(
        'Curso',
        on_delete=models.CASCADE,
        related_name='registros_asistencia_maestros'
    )
    fecha = models.DateField(default=timezone.now)
    hora_ingreso = models.TimeField(null=True, blank=True)
    hora_salida = models.TimeField(null=True, blank=True)
    ausente = models.BooleanField(default=False)  # NUEVO CAMPO
    
    class Meta:
        unique_together = ['maestro', 'curso', 'fecha']
        ordering = ['-fecha', 'curso__nombre', '-hora_ingreso']
    
    def __str__(self):
        estado = "AUSENTE" if self.ausente else "PRESENTE"
        return f"{self.maestro} - {self.curso.nombre} - {self.fecha} - {estado}"
    
    @property
    def estado_asistencia(self):
        """Devuelve el estado de asistencia del maestro"""
        if self.ausente:
            return "ausente"
        elif self.hora_ingreso and self.hora_salida:
            return "completo"
        elif self.hora_ingreso:
            return "ingreso_registrado"
        else:
            return "sin_registro"

class RegistroRetiroAlumno(models.Model):
    """Registro de retiro de alumnos"""
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='registros_retiro')
    familiar = models.ForeignKey(Familiar, on_delete=models.CASCADE, related_name='retiros_realizados')
    maestro = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        limit_choices_to={'es_maestro': True},
        related_name='retiros_registrados'
    )
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='retiros_curso')
    fecha = models.DateField(default=timezone.now)
    hora_retiro = models.TimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-fecha', '-hora_retiro']
    
    def __str__(self):
        return f"{self.alumno} retirado por {self.familiar} - {self.fecha}"

class RegistroAsistenciaAlumno(models.Model):
    """Registro de asistencia diaria de alumnos"""
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='registros_asistencia')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='registros_asistencia')
    maestro = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        limit_choices_to={'es_maestro': True},
        related_name='asistencias_registradas'
    )
    fecha = models.DateField(default=timezone.now)
    presente = models.BooleanField(default=False)
    hora_llegada = models.TimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['alumno', 'fecha']  # Un registro por alumno por día
        ordering = ['-fecha', 'alumno__apellido', 'alumno__nombre']

    def __str__(self):
        return f"{self.alumno} - {self.fecha} - {'Presente' if self.presente else 'Ausente'}"
    @classmethod
    def obtener_estadisticas_ausencias(cls, fecha_inicio=None, fecha_fin=None, curso=None):
        """
        Obtiene estadísticas de ausencias para un período
        """
        queryset = cls.objects.all()
        
        if fecha_inicio:
            queryset = queryset.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            queryset = queryset.filter(fecha__lte=fecha_fin)
        if curso:
            queryset = queryset.filter(curso=curso)
        
        total_registros = queryset.count()
        ausencias = queryset.filter(presente=False).count()
        presencias = queryset.filter(presente=True).count()
        
        return {
            'total_registros': total_registros,
            'ausencias': ausencias,
            'presencias': presencias,
            'porcentaje_ausencias': (ausencias / total_registros * 100) if total_registros > 0 else 0,
            'porcentaje_presencias': (presencias / total_registros * 100) if total_registros > 0 else 0
        }


class CuotaCurso(models.Model):
    """Cuotas mensuales de cada curso"""
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='cuotas')
    mes = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    año = models.PositiveIntegerField()
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    
    # NUEVO CAMPO: Fecha de vencimiento específica para esta cuota
    fecha_vencimiento = models.DateField(
        help_text="Fecha límite para pagar esta cuota sin atraso"
    )
    
    class Meta:
        unique_together = ['curso', 'mes', 'año']
        ordering = ['-año', '-mes']
    
    def save(self, *args, **kwargs):
        # Auto-calcular fecha de vencimiento si no se proporciona
        if not self.fecha_vencimiento:
            self.fecha_vencimiento = self.curso.get_fecha_vencimiento(self.mes, self.año)
        super().save(*args, **kwargs)
    
    @property
    def esta_vencida(self):
        """Verifica si la cuota está vencida"""
        return timezone.now().date() > self.fecha_vencimiento
    
    @property
    def dias_vencida(self):
        """Calcula cuántos días lleva vencida la cuota"""
        if self.esta_vencida:
            return (timezone.now().date() - self.fecha_vencimiento).days
        return 0
    
    def get_alumnos_deudores(self):
        """Obtiene alumnos del curso que no han pagado esta cuota"""
        return self.curso.alumnos.exclude(
            pagos__cuota=self
        )
    
    def marcar_deudores_automaticamente(self):
        """
        Marca como deudores a los alumnos que no pagaron antes del vencimiento
        """
        if not self.esta_vencida:
            return 0, "La cuota aún no está vencida"
        
        alumnos_deudores = self.get_alumnos_deudores()
        deudores_marcados = 0
        
        for alumno in alumnos_deudores:
            # Crear o actualizar registro de deudor
            deudor, created = DeudorCuota.objects.get_or_create(
                alumno=alumno,
                cuota=self,
                defaults={
                    'fecha_vencimiento': self.fecha_vencimiento,
                    'dias_atraso': self.dias_vencida,
                    'monto_adeudado': self.monto
                }
            )
            
            if not created:
                # Actualizar días de atraso si ya existía
                deudor.dias_atraso = self.dias_vencida
                deudor.save()
            
            deudores_marcados += 1
        
        return deudores_marcados, f"Marcados {deudores_marcados} alumnos como deudores"
    
    def __str__(self):
        meses = [
            '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]
        return f"{self.curso} - {meses[self.mes]} {self.año}: ${self.monto}"
    
class DeudorCuota(models.Model):
    """Registro de alumnos deudores de cuotas"""
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='deudas')
    cuota = models.ForeignKey(CuotaCurso, on_delete=models.CASCADE, related_name='deudores')
    fecha_vencimiento = models.DateField()
    fecha_marcado_deudor = models.DateTimeField(auto_now_add=True)
    dias_atraso = models.PositiveIntegerField(default=0)
    monto_adeudado = models.DecimalField(max_digits=10, decimal_places=2)
    pagado = models.BooleanField(default=False)
    fecha_pago = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['alumno', 'cuota']
        ordering = ['-fecha_marcado_deudor']
    
    @property
    def dias_atraso_actual(self):
        """Calcula los días de atraso actuales"""
        if self.pagado:
            return self.dias_atraso  # Mantener los días que tenía cuando pagó
        return (timezone.now().date() - self.fecha_vencimiento).days
    
    def marcar_como_pagado(self):
        """Marca la deuda como pagada"""
        self.pagado = True
        self.fecha_pago = timezone.now()
        self.dias_atraso = self.dias_atraso_actual
        self.save()
    
    def __str__(self):
        estado = "PAGADO CON ATRASO" if self.pagado else f"DEUDOR ({self.dias_atraso_actual} días)"
        return f"{self.alumno} - {self.cuota} - {estado}"
# Método de clase para procesar vencimientos masivos
@classmethod
def procesar_vencimientos_masivos(cls, fecha=None):
    """
    Procesa todas las cuotas vencidas y marca deudores automáticamente
    """
    if fecha is None:
        fecha = timezone.now().date()
    
    # Obtener cuotas vencidas que no han sido procesadas recientemente
    cuotas_vencidas = cls.objects.filter(
        fecha_vencimiento__lt=fecha
    )
    
    total_deudores = 0
    cuotas_procesadas = 0
    resultados = []
    
    for cuota in cuotas_vencidas:
        deudores_marcados, mensaje = cuota.marcar_deudores_automaticamente()
        
        if deudores_marcados > 0:
            total_deudores += deudores_marcados
            cuotas_procesadas += 1
        
        resultados.append({
            'cuota': str(cuota),
            'deudores_marcados': deudores_marcados,
            'mensaje': mensaje
        })
    
    return {
        'success': True,
        'message': f'Proceso completado: {cuotas_procesadas} cuotas procesadas, {total_deudores} deudores marcados',
        'total_deudores': total_deudores,
        'cuotas_procesadas': cuotas_procesadas,
        'resultados': resultados,
        'fecha': fecha.strftime('%Y-%m-%d')
    }
    CuotaCurso.procesar_vencimientos_masivos = procesar_vencimientos_masivos

class PagoCuota(models.Model):
    """Registro de pagos de cuotas"""
    ESTADO_PAGO = [
        ('a_tiempo', 'Pagado a tiempo'),
        ('con_atraso', 'Pagado con atraso'),
    ]
    
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='pagos')
    cuota = models.ForeignKey(CuotaCurso, on_delete=models.CASCADE, related_name='pagos')
    familiar = models.ForeignKey(Familiar, on_delete=models.CASCADE, related_name='pagos_realizados')
    fecha_pago = models.DateField(default=timezone.now)
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2)
    
    # NUEVO CAMPO: Estado del pago
    estado_pago = models.CharField(
        max_length=20, 
        choices=ESTADO_PAGO,
        default='a_tiempo'
    )
    
    # NUEVO CAMPO: Días de atraso al momento del pago
    dias_atraso_pago = models.PositiveIntegerField(
        default=0,
        help_text="Días de atraso que tenía cuando se realizó el pago"
    )
    
    class Meta:
        unique_together = ['alumno', 'cuota']
        ordering = ['-fecha_pago']
    
    def save(self, *args, **kwargs):
        # Auto-determinar estado del pago
        if self.fecha_pago > self.cuota.fecha_vencimiento:
            self.estado_pago = 'con_atraso'
            self.dias_atraso_pago = (self.fecha_pago - self.cuota.fecha_vencimiento).days
        else:
            self.estado_pago = 'a_tiempo'
            self.dias_atraso_pago = 0
        
        super().save(*args, **kwargs)
        
        # Si había un registro de deudor, marcarlo como pagado
        try:
            deudor = DeudorCuota.objects.get(alumno=self.alumno, cuota=self.cuota)
            deudor.marcar_como_pagado()
        except DeudorCuota.DoesNotExist:
            pass
    
    @property
    def descripcion_estado(self):
        """Descripción legible del estado del pago"""
        if self.estado_pago == 'con_atraso':
            return f"Pagado con {self.dias_atraso_pago} días de atraso"
        return "Pagado a tiempo"
    
    def __str__(self):
        return f"Pago de {self.alumno} - {self.cuota} ({self.descripcion_estado})"
# Modelo para tokens de recuperación
class PasswordResetToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)
    
    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(hours=24)
    
    def __str__(self):
        return f"Token para {self.user.username}"

# Option 1: Add to your models.py file
# jardinaplicacion/models.py

import secrets
import string
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta

def generate_random_token(length=32):
    """Generate a cryptographically secure random token"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# Alternative: Generate a 6-digit numeric code for easier user input
def generate_recovery_code():
    """Generate a 6-digit recovery code"""
    return ''.join(secrets.choice(string.digits) for _ in range(6))
