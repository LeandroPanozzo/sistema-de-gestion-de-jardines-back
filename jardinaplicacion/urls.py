from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from . import views
from .views import DeudorCuotaViewSet
# Router para los ViewSets
router = DefaultRouter()
router.register(r'users', views.CustomUserViewSet)
router.register(r'ciclos-lectivos', views.CicloLectivoViewSet)
router.register(r'cursos', views.CursoViewSet)
router.register(r'alumnos', views.AlumnoViewSet)
router.register(r'familiares', views.FamiliarViewSet)
router.register(r'asistencia-maestros', views.RegistroAsistenciaMaestroViewSet)
router.register(r'retiros-alumnos', views.RegistroRetiroAlumnoViewSet)
router.register(r'cuotas', views.CuotaCursoViewSet)
router.register(r'pagos', views.PagoCuotaViewSet)
router.register(r'configuracion', views.ConfiguracionSistemaViewSet)  # Agregado
router.register(r'asistencia-alumnos', views.RegistroAsistenciaAlumnoViewSet)
router.register(r'avisos-directivo', views.AvisoDirectivoViewSet)
router.register(r'deudores', DeudorCuotaViewSet)
urlpatterns = [
    # URLs de autenticación
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/token/', obtain_auth_token, name='api_token_auth'),
    path('auth/me/', views.me_view, name='me'),
    path('auth/forgot-password/', views.forgot_password, name='forgot_password'),
    path('auth/forgot-username/', views.forgot_username, name='forgot_username'),
    path('auth/reset-password/', views.reset_password, name='reset_password'),
    path('auth/verify-reset-token/', views.verify_reset_token, name='verify_reset_token'),
    # Incluir todas las rutas del router
    path('', include(router.urls)),
]