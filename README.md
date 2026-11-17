# Sistema de Gestión de Inventarios (StockApp)

Aplicación web desarrollada con **Python y Django** para administrar productos, controlar existencias y registrar movimientos de inventario, con seguimiento del consumo de materiales por proyecto.

> **Estado:** En desarrollo activo. Proyecto personal de aprendizaje y mejora continua. Pasó por una refactorización incremental del dominio de inventario: reorganización por capas, integridad a nivel de base de datos y optimización de consultas, con paridad de comportamiento verificada en cada paso (ver historial de commits).

## Funcionalidades

- **Dashboard** (`/`): alertas de stock bajo (total + los 6 más severos), últimos 10 movimientos, últimos 5 proyectos y feed de actividad reciente.
- **Productos** (`/productos/lista/`): catálogo con categoría, unidad, almacén y stock calculado en tiempo real.
- **Proyectos** (`/proyectos/lista/`, `/proyectos/detalle/<pk>/`): ficha con consumo de materiales por proyecto y empleados involucrados.
- **Movimientos** (`/movimientos/`, `/movimientos/<pk>/`, `/movimientos/nuevo/`): historial con filtros, detalle de solo lectura y alta de entradas, salidas y ajustes. El alta exige un usuario staff; el stock insuficiente se muestra como error de formulario (sin errores 500).
- **Admin Django** (`/admin/`) en español para gestionar todas las entidades. Los movimientos son inmutables (sin borrado).
- **Trazabilidad**: motivo, proyecto, empleado, almacén y usuario que registró cada movimiento.

## Arquitectura y decisiones clave

- **El stock es derivado, nunca almacenado**: se calcula por agregación de movimientos mediante una única expresión ORM (`signed_quantity_expression`/`stock_expression` en `inventory/models.py`).
- **Escrituras a través de un service**: `register_movement()` (`inventory/services.py`) envuelve el caso de uso en `transaction.atomic()`. Las reglas de fila viven en `Movement.clean()`/`save()`.
- **Integridad a nivel de base de datos**: `CheckConstraint`s en `Movement` (cantidad > 0 y coherencia del tipo de ajuste) protegen caminos que evitan Python (`bulk_create`, `update()`). La regla "stock nunca negativo" es entre filas y se valida en `save()`.
- **Selectores para lecturas multi-modelo**: el feed de actividad vive en `inventory/selectors.py`.
- **Frontend sin framework**: plantillas Django + CSS propio (`static/css/`).

## Modelo de datos

| Entidad | Propósito |
| --- | --- |
| `Category` | Clasificar los productos. |
| `Unit` | Unidades de medida. |
| `Warehouse` | Almacenes. |
| `Product` | Materiales del inventario (SKU único, stock mínimo). |
| `Department` / `Employee` | Áreas y empleados que registran movimientos. |
| `Project` | Proyectos asociados al consumo de material. |
| `Movement` | Entradas, salidas y ajustes; fuente única de verdad del stock. |

## Reglas de negocio

1. La cantidad de un movimiento debe ser mayor que cero (modelo + `CheckConstraint`).
2. Una salida no puede dejar el stock en negativo.
3. Las salidas requieren un proyecto **aprobado (en curso)** o un motivo documentado.
4. Las entradas requieren un proyecto o un motivo.
5. Los ajustes requieren motivo y tipo de ajuste (aumento/disminución), y el tipo solo aplica a ajustes (modelo + `CheckConstraint`).
6. Todo movimiento requiere un empleado; el almacén se hereda del producto.
7. Los registros padre (categorías, unidades, productos, proyectos) no se pueden borrar si tienen movimientos asociados (`PROTECT`).

## Tecnologías

- Python 3.10
- Django 5.2
- Django ORM (QuerySets, agregaciones, constraints)
- PostgreSQL 14 (base de datos principal) con SQLite como fallback de desarrollo
- Plantillas Django + CSS propio

## Instalación local

Requisitos: Python 3.10+ y Git.

```bash
# 1. Clonar
git clone https://github.com/jesus010795/stock-app.git
cd stock-app

# 2. Entorno virtual e instalación de dependencias
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Migraciones
python manage.py migrate

# 4. Usuario administrador (opcional)
python manage.py createsuperuser

# 5. Servidor de desarrollo
python manage.py runserver
```

Abre `http://127.0.0.1:8000/`.

### Base de datos

Sin configuración adicional se usa **SQLite** (`db.sqlite3`, ideal para un clon rápido). Para usar **PostgreSQL** (motor principal de desarrollo):

```bash
export POSTGRES_DB=stockapp POSTGRES_USER=stockapp POSTGRES_PASSWORD=stockapp
python manage.py migrate
```

La conexión usa `localhost:5432` por defecto (`POSTGRES_HOST`/`POSTGRES_PORT` opcionales). `SECRET_KEY` se lee de la variable de entorno `DJANGO_SECRET_KEY` (con un fallback de desarrollo).

> `db.sqlite3`, `media/`, `docs/` y `commits.txt` están en `.gitignore`: este repositorio es el código, no los datos locales ni la bitácora de trabajo.

## Acceso

Las páginas de lectura (dashboard, historial, productos, proyectos y empleados) se consultan sin sesión. Registrar un movimiento exige iniciar sesión en `/accounts/login/` con un usuario activo y `is_staff=True`.

Las cuentas se crean desde el admin. Marca **Es staff** y no concedas permisos de modelo salvo que esa persona deba administrar: `is_staff` también abre `/admin/`, pero sin permisos de modelo el admin no deja editar registros.

Cerrar sesión se hace desde el menú superior (POST con CSRF). No hay registro público ni recuperación de contraseña.

## Tests

```bash
python manage.py test inventory products stockapp
```

95 tests cubren: formulario y vista de movimientos, autorización del alta, modelo y reglas de negocio, service transaccional, constraints de base de datos, stock por producto, selector de actividad, bloque de stock bajo del dashboard y login staff. Hay que nombrar `stockapp`: es el paquete del proyecto, no una app instalada, y `manage.py test` sin etiquetas no descubre `stockapp/tests.py`.

## Rutas principales

| Ruta | Descripción |
| --- | --- |
| `/` | Dashboard |
| `/productos/lista/` | Listado de productos |
| `/proyectos/lista/` y `/proyectos/detalle/<pk>/` | Proyectos |
| `/movimientos/` y `/movimientos/<pk>/` | Historial y detalle de movimientos |
| `/movimientos/nuevo/` | Alta de movimiento (requiere staff) |
| `/accounts/login/` | Inicio de sesión (solo staff) |
| `/admin/` | Administración de Django |

## Próximas mejoras

- [ ] Migración del admin al service `register_movement` (AP-11).

## Autor

Proyecto personal desarrollado como parte del aprendizaje y la práctica de desarrollo de software con Python y Django.

## Licencia

Por definir. No se asume una licencia de código abierto hasta que se agregue un archivo `LICENSE` al repositorio.
