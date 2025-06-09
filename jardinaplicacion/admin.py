from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    CustomUser, CicloLectivo, Curso, Alumno, Familiar,
    RegistroAsistenciaMaestro, RegistroRetiroAlumno, CuotaCurso, PagoCuota,
    ConfiguracionSistema
)


# Modelo proxy para gestión de trabajadores
class Trabajador(CustomUser):
    """Modelo proxy para gestionar habilitaciones de trabajadores"""
    class Meta:
        proxy = True
        verbose_name = "Trabajador"
        verbose_name_plural = "Trabajadores"


@admin.register(Trabajador)
class TrabajadorAdmin(admin.ModelAdmin):
    """Admin para habilitar usuarios como maestros o directivos"""
    list_display = ('nombre_completo', 'username', 'dni', 'rol_badges', 'habilitaciones_actuales', 'is_active')
    list_filter = ('es_maestro', 'es_directivo', 'is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'dni', 'email')
    ordering = ('first_name', 'last_name')
    
    fieldsets = (
        ('Información del Usuario', {
            'fields': ('username', 'first_name', 'last_name', 'email')
        }),
        ('Información Personal', {
            'fields': ('dni', 'telefono', 'direccion', 'fecha_nacimiento')
        }),
        ('Habilitaciones de Trabajo', {
            'fields': ('es_maestro', 'es_directivo'),
            'classes': ('wide',),
            'description': 'Marque las casillas para habilitar al usuario en los roles correspondientes.'
        }),
        ('Estado', {
            'fields': ('is_active',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('username', 'first_name', 'last_name', 'email', 'dni', 'telefono', 'direccion', 'fecha_nacimiento')
    
    def get_queryset(self, request):
        """Mostrar solo usuarios que no son superusuarios"""
        return super().get_queryset(request).filter(is_superuser=False)
    
    def nombre_completo(self, obj):
        return f"{obj.first_name} {obj.last_name}" if obj.first_name or obj.last_name else obj.username
    nombre_completo.short_description = 'Nombre Completo'
    
    def rol_badges(self, obj):
        badges = []
        if obj.es_maestro:
            badges.append('<span style="background: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">MAESTRO</span>')
        if obj.es_directivo:
            badges.append('<span style="background: #007bff; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">DIRECTIVO</span>')
        return mark_safe(' '.join(badges)) if badges else '<span style="color: #6c757d;">Sin roles</span>'
    rol_badges.short_description = 'Roles Asignados'
    
    def habilitaciones_actuales(self, obj):
        habilitaciones = []
        if obj.es_maestro:
            habilitaciones.append('Maestro')
        if obj.es_directivo:
            habilitaciones.append('Directivo')
        
        if habilitaciones:
            return ', '.join(habilitaciones)
        return 'Sin habilitaciones'
    habilitaciones_actuales.short_description = 'Habilitaciones'
    
    def has_add_permission(self, request):
        """No permitir crear usuarios desde esta vista"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """No permitir eliminar usuarios desde esta vista"""
        return False
    
    def save_model(self, request, obj, form, change):
        """Guardar solo los cambios en las habilitaciones"""
        if change:  # Solo si estamos editando
            super().save_model(request, obj, form, change)
            
            # Mensaje personalizado según los cambios
            roles = []
            if obj.es_maestro:
                roles.append('Maestro')
            if obj.es_directivo:
                roles.append('Directivo')
            
            if roles:
                self.message_user(
                    request,
                    f'Usuario {obj.username} habilitado como: {", ".join(roles)}',
                    level='SUCCESS'
                )
            else:
                self.message_user(
                    request,
                    f'Se removieron todas las habilitaciones de {obj.username}',
                    level='WARNING'
                )


@admin.register(ConfiguracionSistema)
class ConfiguracionSistemaAdmin(admin.ModelAdmin):
    list_display = ('estado_registro', 'fecha_actualizacion', 'actualizado_por_nombre')
    list_filter = ('registro_asistencia_habilitado', 'fecha_actualizacion')
    readonly_fields = ('fecha_actualizacion',)
    
    def estado_registro(self, obj):
        if obj.registro_asistencia_habilitado:
            return format_html('<span style="color: green;">✓ Habilitado</span>')
        return format_html('<span style="color: red;">✗ Deshabilitado</span>')
    estado_registro.short_description = 'Estado del Registro'
    
    def actualizado_por_nombre(self, obj):
        if obj.actualizado_por:
            return f"{obj.actualizado_por.first_name} {obj.actualizado_por.last_name}"
        return "Sin actualizar"
    actualizado_por_nombre.short_description = 'Actualizado por'
    
    def save_model(self, request, obj, form, change):
        obj.actualizado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'dni', 'rol_badges', 'is_active')
    list_filter = ('es_maestro', 'es_directivo', 'is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'dni', 'email')
    ordering = ('username',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Información Personal Adicional', {
            'fields': ('dni', 'telefono', 'direccion', 'fecha_nacimiento')
        }),
        ('Habilitaciones del Sistema', {
            'fields': ('es_maestro', 'es_directivo'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Personal', {
            'fields': ('first_name', 'last_name', 'email', 'dni', 'telefono', 'direccion', 'fecha_nacimiento')
        }),
        ('Habilitaciones', {
            'fields': ('es_maestro', 'es_directivo')
        }),
    )
    
    def rol_badges(self, obj):
        badges = []
        if obj.es_maestro:
            badges.append('<span style="background: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">MAESTRO</span>')
        if obj.es_directivo:
            badges.append('<span style="background: #007bff; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">DIRECTIVO</span>')
        if obj.is_superuser:
            badges.append('<span style="background: #dc3545; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">ADMIN</span>')
        return mark_safe(' '.join(badges)) if badges else '-'
    rol_badges.short_description = 'Roles'


@admin.register(CicloLectivo)
class CicloLectivoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'inicio', 'finalizacion', 'duracion_dias', 'estado')
    list_filter = ('inicio', 'finalizacion')
    date_hierarchy = 'inicio'
    ordering = ('-inicio',)
    
    def duracion_dias(self, obj):
        return (obj.finalizacion - obj.inicio).days
    duracion_dias.short_description = 'Duración (días)'
    
    def estado(self, obj):
        from datetime import date
        hoy = date.today()
        if hoy < obj.inicio:
            return format_html('<span style="color: blue;">Próximo</span>')
        elif obj.inicio <= hoy <= obj.finalizacion:
            return format_html('<span style="color: green;">Activo</span>')
        else:
            return format_html('<span style="color: gray;">Finalizado</span>')
    estado.short_description = 'Estado'


class AlumnoInline(admin.TabularInline):
    model = Alumno
    extra = 0
    fields = ('nombre', 'apellido', 'dni', 'fecha_nacimiento', 'edad_display')
    readonly_fields = ('edad_display',)
    
    def edad_display(self, obj):
        return f"{obj.edad} años" if obj.edad else "-"
    edad_display.short_description = 'Edad'


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'turno', 'edad_sala', 'ciclo_lectivo', 'cupos_info', 'maestros_count')
    list_filter = ('turno', 'edad_sala', 'ciclo_lectivo')
    search_fields = ('nombre',)
    filter_horizontal = ('maestros',)
    inlines = [AlumnoInline]
    
    def cupos_info(self, obj):
        disponibles = obj.cupos_disponibles
        total = obj.cupo_habilitado
        inscriptos = obj.alumnos_inscriptos
        
        if disponibles > 0:
            color = 'green'
        elif disponibles == 0:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{}/{} ({})</span>',
            color, inscriptos, total, 
            f"{disponibles} disponibles" if disponibles >= 0 else "Excedido"
        )
    cupos_info.short_description = 'Cupos (Inscriptos/Total)'
    
    def maestros_count(self, obj):
        count = obj.maestros.count()
        if count == 0:
            return format_html('<span style="color: red;">Sin maestros</span>')
        return f"{count} maestro{'s' if count > 1 else ''}"
    maestros_count.short_description = 'Maestros'


class FamiliarInline(admin.StackedInline):
    model = Familiar
    extra = 1
    fields = (('nombre', 'apellido'), ('dni', 'relacion_con_alumno'), 
              ('telefono', 'mail'), 'direccion')


@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'dni', 'edad_display', 'curso', 'familiares_count')
    list_filter = ('curso', 'curso__turno', 'fecha_nacimiento')
    search_fields = ('nombre', 'apellido', 'dni')
    date_hierarchy = 'fecha_nacimiento'
    inlines = [FamiliarInline]
    
    def nombre_completo(self, obj):
        return f"{obj.nombre} {obj.apellido}"
    nombre_completo.short_description = 'Nombre Completo'
    
    def edad_display(self, obj):
        return f"{obj.edad} años"
    edad_display.short_description = 'Edad'
    
    def familiares_count(self, obj):
        count = obj.familiares.count()
        return f"{count} familiar{'es' if count != 1 else ''}"
    familiares_count.short_description = 'Familiares'


@admin.register(Familiar)
class FamiliarAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'relacion_con_alumno', 'alumno', 'telefono', 'dni')
    list_filter = ('relacion_con_alumno', 'alumno__curso')
    search_fields = ('nombre', 'apellido', 'dni', 'alumno__nombre', 'alumno__apellido')
    
    def nombre_completo(self, obj):
        return f"{obj.nombre} {obj.apellido}"
    nombre_completo.short_description = 'Nombre Completo'


@admin.register(RegistroAsistenciaMaestro)
class RegistroAsistenciaMaestroAdmin(admin.ModelAdmin):
    list_display = ('maestro', 'fecha', 'hora_ingreso', 'hora_salida', 'horas_trabajadas', 'estado_registro')
    list_filter = ('fecha', 'maestro')
    search_fields = ('maestro__first_name', 'maestro__last_name')
    date_hierarchy = 'fecha'
    ordering = ('-fecha', '-hora_ingreso')
    
    def horas_trabajadas(self, obj):
        if obj.hora_salida and obj.hora_ingreso:
            from datetime import datetime, date
            inicio = datetime.combine(date.today(), obj.hora_ingreso)
            fin = datetime.combine(date.today(), obj.hora_salida)
            diff = fin - inicio
            horas = diff.total_seconds() / 3600
            return f"{horas:.1f}h"
        return "-"
    horas_trabajadas.short_description = 'Horas trabajadas'
    
    def estado_registro(self, obj):
        if obj.hora_salida:
            return format_html('<span style="color: green;">✓ Completo</span>')
        return format_html('<span style="color: orange;">⏳ Sin salida</span>')
    estado_registro.short_description = 'Estado'


@admin.register(RegistroRetiroAlumno)
class RegistroRetiroAlumnoAdmin(admin.ModelAdmin):
    list_display = ('alumno', 'familiar', 'fecha', 'hora_retiro', 'maestro', 'curso_alumno')
    list_filter = ('fecha', 'alumno__curso', 'familiar__relacion_con_alumno')
    search_fields = ('alumno__nombre', 'alumno__apellido', 'familiar__nombre', 'familiar__apellido')
    date_hierarchy = 'fecha'
    ordering = ('-fecha', '-hora_retiro')
    
    def curso_alumno(self, obj):
        return obj.alumno.curso
    curso_alumno.short_description = 'Curso'


@admin.register(CuotaCurso)
class CuotaCursoAdmin(admin.ModelAdmin):
    list_display = ('curso', 'mes_nombre', 'año', 'monto', 'pagos_realizados', 'estado_cobranza')
    list_filter = ('año', 'mes', 'curso')
    search_fields = ('curso__nombre',)
    ordering = ('-año', '-mes')
    
    def mes_nombre(self, obj):
        meses = [
            '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]
        return meses[obj.mes]
    mes_nombre.short_description = 'Mes'
    
    def pagos_realizados(self, obj):
        return obj.pagos.count()
    pagos_realizados.short_description = 'Pagos'
    
    def estado_cobranza(self, obj):
        pagos = obj.pagos.count()
        alumnos = obj.curso.alumnos_inscriptos
        if alumnos == 0:
            return format_html('<span style="color: gray;">Sin alumnos</span>')
        
        porcentaje = (pagos / alumnos) * 100
        if porcentaje == 100:
            color = 'green'
            texto = '100% Pagado'
        elif porcentaje >= 75:
            color = 'orange'
            texto = f'{porcentaje:.0f}% Pagado'
        else:
            color = 'red'
            texto = f'{porcentaje:.0f}% Pagado'
        
        return format_html(f'<span style="color: {color};">{texto}</span>')
    estado_cobranza.short_description = 'Estado'


@admin.register(PagoCuota)
class PagoCuotaAdmin(admin.ModelAdmin):
    list_display = ('alumno', 'cuota_info', 'monto_pagado', 'familiar', 'fecha_pago', 'diferencia_monto')
    list_filter = ('fecha_pago', 'cuota__año', 'cuota__mes', 'alumno__curso')
    search_fields = ('alumno__nombre', 'alumno__apellido', 'familiar__nombre', 'familiar__apellido')
    date_hierarchy = 'fecha_pago'
    ordering = ('-fecha_pago',)
    
    def cuota_info(self, obj):
        meses = [
            '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]
        return f"{meses[obj.cuota.mes]} {obj.cuota.año} - {obj.cuota.curso.nombre}"
    cuota_info.short_description = 'Cuota'
    
    def diferencia_monto(self, obj):
        diferencia = obj.monto_pagado - obj.cuota.monto
        if diferencia > 0:
            return format_html('<span style="color: green;">+${}</span>', diferencia)
        elif diferencia < 0:
            return format_html('<span style="color: red;">-${}</span>', abs(diferencia))
        else:
            return format_html('<span style="color: gray;">Exacto</span>')
    diferencia_monto.short_description = 'Diferencia'


# Personalización del sitio admin
admin.site.site_header = "Administración del Jardín"
admin.site.site_title = "Admin Jardín"
admin.site.index_title = "Panel de Administración"