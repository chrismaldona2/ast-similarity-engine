# Motor de búsqueda de similitud de funciones mediante AST

Motor de análisis estático orientado a identificar funciones de Python con estructuras similares. El sistema utiliza el Árbol de Sintaxis Abstracta (AST) para representar el código, normaliza determinados identificadores y elementos sintácticos, y transforma los árboles en secuencias de tokens que pueden compararse mediante métricas de similitud.

El proyecto se desarrolla en el marco de la cátedra **Lenguajes Formales y Autómatas**, de la Universidad Católica de Santiago del Estero (UCSE), durante el ciclo lectivo 2026.

## Arquitectura del proyecto

| Archivo o directorio | Responsabilidad                                                                                                     |
| :------------------- | :------------------------------------------------------------------------------------------------------------------ |
| `src/models.py`      | Define las estructuras de datos utilizadas para representar las funciones analizadas.                               |
| `src/extractor.py`   | Recorre directorios y extrae definiciones de funciones a partir de los AST de los archivos Python.                  |
| `src/normalizer.py`  | Normaliza identificadores y literales, y aplica los criterios de limpieza sintáctica definidos para la comparación. |
| `src/serializer.py`  | Recorre los AST normalizados en preorden y genera secuencias de tokens.                                             |
| `src/similarity.py`  | Implementa las métricas de similitud utilizadas para comparar las representaciones de las funciones.                |
| `src/engine.py`      | Coordina la extracción, el procesamiento y la comparación de funciones, y organiza los resultados.                  |
| `find_similar.py`    | Proporciona la interfaz de línea de comandos (CLI) principal del motor.                                             |
| `generate_corpus.py` | Script auxiliar que genera el corpus de prueba en el directorio `examples/` para evaluar la herramienta.            |
| `tests/`             | Contiene las pruebas automatizadas (unitarias y de integración) del proyecto.                                       |
| `examples/`          | Contiene archivos Python utilizados para evaluar y demostrar el comportamiento del sistema (casos base).            |
| `lab/`               | Contiene scripts exploratorios y de calibración empírica de umbrales y métricas (`calibrate.py`).                   |
| `docs/`              | Reúne la documentación técnica y los análisis de diseño.                                                            |

## Requisitos

- Python 3.10 o superior.
- `pytest`, para ejecutar las pruebas automatizadas.

## Instalación

Se recomienda crear un entorno virtual para instalar las dependencias del proyecto de manera aislada.

```bash
python -m venv .venv

```

En Windows, activar el entorno virtual con:

```powershell
.venv\Scripts\Activate.ps1

```

Instalar las dependencias:

```bash
python -m pip install -r requirements.txt

```

## Pruebas

Para ejecutar las pruebas automatizadas desde el directorio raíz del proyecto:

```bash
pytest -v

```

## Uso

El motor se ejecuta a través del script `find_similar.py`. Para ver todas las opciones y métricas disponibles:

```bash
python find_similar.py --help

```

### Ejemplos de ejecución

**1. Buscar similitudes de una función dentro del repositorio**
Busca las funciones más similares a `average` (definida en el archivo `clones_renamed.py`) dentro de la carpeta `examples/`:

```bash
python find_similar.py --dir ./examples --funcion clones_renamed.py:average --top 5

```

**2. Buscar usando un archivo externo como consulta**
Evalúa un archivo de consulta contra el directorio objetivo y muestra solo las funciones que superan el umbral de similitud (candidatas a duplicado):

```bash
python find_similar.py --dir ./examples --query-file consulta.py --only-candidates

```

**Opciones destacadas:**

- `--metric {jaccard,levenshtein}`: Cambia la métrica de similitud (por defecto: `jaccard` con umbral calibrado de 0.50).
- `--index-vars` / `--no-index-vars`: Activa o desactiva la preservación estricta de la identidad de variables (`VAR1`, `VAR2`). Por defecto está desactivado (`--no-index-vars` -> `VAR`) para tolerar mejor el reordenamiento de líneas independientes.

## Documentación técnica

La documentación complementaria se encuentra en el directorio `docs/`.

- **[Notas de diseño](docs/design_notes.md):** detalla los fundamentos teóricos, los criterios adoptados para el procesamiento del AST y las decisiones de diseño, junto con sus justificaciones y limitaciones.
