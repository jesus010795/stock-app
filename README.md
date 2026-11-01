# Sistema de Gestión de Inventarios (StockApp)

Aplicación web desarrollada con **Python y Django** para administrar productos, controlar existencias y registrar movimientos de inventario, con seguimiento del consumo de materiales por proyecto.

> **Estado:** En desarrollo activo. Proyecto personal de aprendizaje y mejora continua.

## Funcionalidades

- **Dashboard** (`/`): alertas de stock bajo (total + los 6 más severos), últimos 10 movimientos, últimos 5 proyectos y feed de actividad reciente.
- **Productos** (`/productos/lista/`): catálogo con categoría, unidad, almacén y stock calculado en tiempo real.
- **Proyectos** (`/proyectos/lista/`, `/proyectos/detalle/<pk>/`): ficha con consumo de materiales por proyecto y empleados involucrados.
- **Movimientos** (`/movimientos/nuevo/`): alta de entradas, salidas y ajustes con validaciones en español; el stock insuficiente se muestra como error de formulario (sin errores 500).
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
- SQLite (base de datos de desarrollo)
- Plantillas Django + CSS propio

## Instalación local

Requisitos: Python 3.10+ y Git.

```bash
# 1. Clonar
git clone https://github.com/jesus010795/stock-app.git
cd stock-app

# 2. Entorno virtual e instalación de Django (aún no hay requirements.txt)
python3 -m venv venv
source venv/bin/activate
pip install Django==5.2

# 3. Migraciones
python manage.py migrate

# 4. Usuario administrador (opcional)
python manage.py createsuperuser

# 5. Servidor de desarrollo
python manage.py runserver
```

Abre `http://127.0.0.1:8000/`.

Configuración sensible: `SECRET_KEY` se lee de la variable de entorno `DJANGO_SECRET_KEY` (con un fallback de desarrollo). Para un entorno distinto al local:

```bash
export DJANGO_SECRET_KEY="tu-clave-secreta"
```

> `db.sqlite3`, `media/`, `docs/` y `commits.txt` están en `.gitignore`: este repositorio es el código, no los datos locales ni la bitácora de trabajo.

## Tests

```bash
python manage.py test inventory products
```

66 tests cubren: formulario y vista de movimientos, modelo y reglas de negocio, service transaccional, constraints de base de datos, stock por producto, selector de actividad y bloque de stock bajo del dashboard.

## Rutas principales

| Ruta | Descripción |
| --- | --- |
| `/` | Dashboard |
| `/productos/lista/` | Listado de productos |
| `/proyectos/lista/` y `/proyectos/detalle/<pk>/` | Proyectos |
| `/movimientos/nuevo/` | Alta de movimiento |
| `/admin/` | Administración de Django |

## Próximas mejoras

- [ ] Autenticación y control de acceso en las vistas públicas (hoy el dashboard y el formulario no requieren login).
- [ ] Historial y detalle de movimientos (rutas ya esbozadas).
- [ ] Evaluar migración a PostgreSQL como fase separada.
- [ ] `requirements.txt` y capturas de pantalla.

## Autor

Proyecto personal desarrollado como parte del aprendizaje y la práctica de desarrollo de software con Python y Django.

## Licencia

Por definir. No se asume una licencia de código abierto hasta que se agregue un archivo `LICENSE` al repositorio.
