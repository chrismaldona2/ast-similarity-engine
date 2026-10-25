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
| `find_similar.py`    | Proporciona la interfaz de línea de comandos (CLI).                                                                 |
| `tests/`             | Contiene las pruebas automatizadas del proyecto.                                                                    |
| `examples/`          | Contiene archivos Python utilizados para evaluar y demostrar el comportamiento del sistema.                         |
| `lab/`               | Contiene scripts exploratorios utilizados para analizar el módulo `ast` de Python.                                  |
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

La interfaz de línea de comandos permite realizar búsquedas de funciones estructuralmente similares. Las opciones disponibles y los ejemplos de ejecución se documentarán una vez definida su interfaz.

## Documentación técnica

La documentación complementaria se encuentra en el directorio `docs/`.

- **[Notas de diseño](docs/design_notes.md):** detalla los fundamentos teóricos, los criterios adoptados para el procesamiento del AST y las decisiones de diseño, junto con sus justificaciones y limitaciones.
