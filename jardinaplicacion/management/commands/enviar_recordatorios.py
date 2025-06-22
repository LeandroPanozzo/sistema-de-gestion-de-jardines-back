import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from jardinaplicacion.models import Familiar, Alumno

class Command(BaseCommand):
    help = 'Envía recordatorios de pago automáticamente'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tipo',
            type=str,
            choices=['inicio_mes', 'vencimiento'],
            help='Tipo de recordatorio a enviar',
            required=True
        )
        parser.add_argument(
            '--fecha',
            type=str,
            help='Fecha específica para probar (formato: YYYY-MM-DD)',
            required=False
        )

    def handle(self, *args, **options):
        tipo_recordatorio = options['tipo']
        fecha_especifica = options.get('fecha')

        if fecha_especifica:
            try:
                fecha_actual = datetime.strptime(fecha_especifica, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Formato de fecha inválido. Use YYYY-MM-DD')
                )
                return
        else:
            fecha_actual = timezone.now().date()

        if tipo_recordatorio == 'inicio_mes':
            self.enviar_recordatorio_inicio_mes(fecha_actual)
        elif tipo_recordatorio == 'vencimiento':
            self.enviar_recordatorio_vencimiento(fecha_actual)

    def enviar_recordatorio_inicio_mes(self, fecha_actual):
        if fecha_actual.day != 1:
            self.stdout.write(
                self.style.WARNING(f'Hoy no es día 1 del mes. Fecha actual: {fecha_actual}')
            )
            return

        self.stdout.write(f'Enviando recordatorios de inicio de mes para {fecha_actual}...')

        alumnos = Alumno.objects.all().prefetch_related('familiares', 'curso')
        correos_enviados = 0
        errores = 0

        for alumno in alumnos:
            familiares_con_email = alumno.familiares.exclude(mail='').exclude(mail__isnull=True)

            for familiar in familiares_con_email:
                try:
                    self.enviar_email_inicio_mes(familiar, alumno, fecha_actual)
                    correos_enviados += 1
                    self.stdout.write(f'✓ Email enviado a {familiar.mail}')
                except Exception as e:
                    errores += 1
                    self.stdout.write(
                        self.style.ERROR(f'✗ Error enviando email a {familiar.mail}: {str(e)}')
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'Proceso completado. Enviados: {correos_enviados}, Errores: {errores}'
            )
        )

    def enviar_recordatorio_vencimiento(self, fecha_actual):
        if fecha_actual.day != 10:
            self.stdout.write(
                self.style.WARNING(f'Hoy no es día 10 del mes. Fecha actual: {fecha_actual}')
            )
            return

        self.stdout.write(f'Enviando recordatorios de vencimiento para {fecha_actual}...')

        alumnos = Alumno.objects.all().prefetch_related('familiares', 'curso')
        correos_enviados = 0
        errores = 0

        for alumno in alumnos:
            familiares_con_email = alumno.familiares.exclude(mail='').exclude(mail__isnull=True)

            for familiar in familiares_con_email:
                try:
                    self.enviar_email_vencimiento(familiar, alumno, fecha_actual)
                    correos_enviados += 1
                    self.stdout.write(f'✓ Email enviado a {familiar.mail}')
                except Exception as e:
                    errores += 1
                    self.stdout.write(
                        self.style.ERROR(f'✗ Error enviando email a {familiar.mail}: {str(e)}')
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'Proceso completado. Enviados: {correos_enviados}, Errores: {errores}'
            )
        )

    def enviar_email_inicio_mes(self, familiar, alumno, fecha_actual):
        meses = [
            '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]

        asunto = f'Recordatorio de Pago - {meses[fecha_actual.month]} {fecha_actual.year}'

        mensaje = f"""
Estimado/a {familiar.nombre} {familiar.apellido},

Le recordamos que está disponible el pago de la cuota mensual para el alumno/a {alumno.nombre} {alumno.apellido}.

Detalles:
- Curso: {alumno.curso.nombre if alumno.curso else "No asignado"}
- Mes: {meses[fecha_actual.month]} {fecha_actual.year}

Para evitar atrasos, recomendamos realizar el pago antes de la fecha límite.

Ante cualquier consulta, no dude en contactarnos.

Saludos cordiales,
Administración del Jardín
        """

        send_mail(
            asunto,
            mensaje,
            settings.EMAIL_HOST_USER,
            [familiar.mail],
            fail_silently=False,
        )

    def enviar_email_vencimiento(self, familiar, alumno, fecha_actual):
        meses = [
            '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]

        asunto = f'ÚLTIMO RECORDATORIO - Vencimiento de Cuota - {meses[fecha_actual.month]} {fecha_actual.year}'
        dias_restantes = (fecha_actual.replace(day=15) - fecha_actual).days  # ejemplo: 15 del mes

        mensaje = f"""
Estimado/a {familiar.nombre} {familiar.apellido},

Este es un recordatorio URGENTE sobre el vencimiento de la cuota mensual del alumno/a {alumno.nombre} {alumno.apellido}.

⚠️ ATENCIÓN: La cuota vence el día 15 del mes (quedan {dias_restantes} días)

Detalles de la cuota PENDIENTE:
- Curso: {alumno.curso.nombre if alumno.curso else "No asignado"}
- Mes: {meses[fecha_actual.month]} {fecha_actual.year}

Para evitar que la cuota quede en estado de atraso, le solicitamos realizar el pago a la brevedad.

Si ya realizó el pago, puede hacer caso omiso a este mensaje.

Ante cualquier consulta, contacte a la administración.

Saludos cordiales,
Administración del Jardín
        """

        send_mail(
            asunto,
            mensaje,
            settings.EMAIL_HOST_USER,
            [familiar.mail],
            fail_silently=False,
        )
