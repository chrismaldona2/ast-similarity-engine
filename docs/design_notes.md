# Notas de diseño y arquitectura

Este documento detalla los fundamentos, análisis y decisiones arquitectónicas del motor de búsqueda de similitud de funciones Python.

## 1. Fundamentos teóricos

- **AST (Árbol de Sintaxis Abstracta):** A diferencia de un árbol de derivación concreto (que incluye paréntesis, dos puntos o indentación), el AST abstrae la estructura sintáctica pura. Se relaciona conceptualmente con los árboles de gramáticas independientes del contexto (Tipo 2).
- **Tabla de símbolos y Ámbitos:** Python liga identificadores al ámbito local (asignaciones, `for`) o los deja libres (`built-ins`). Aislar el origen de un identificador es vital para una normalización fiel.
- **Recorrido en preorden:** Proyectar un árbol a una secuencia exige un orden determinista. Como `ast.walk()` realiza un recorrido en anchura (BFS) y necesitamos profundidad preorden (DFS), implementamos un recorrido explícito vía `ast.iter_child_nodes()`.

---

## 2. Decisiones de diseño

### 2.1. Serialización (Tokens)

El recorrido emite un token por nodo para armar secuencias comparables:

- **Estructurales** (`If`, `Return`, `BinOp`): Emiten su tipo (ej. `Return`).
- **Con valor** (`Name`, `Constant`, `Attribute`, `ExceptHandler`): Emiten `Tipo:valor` (ej. `Name:VAR`, `Attribute:append`).
- **Importaciones:** `ImportFrom` emite el tipo y módulo (ej. `ImportFrom:os`); `alias` emite el nombre del módulo.
- **Modo sin índice (`index_vars=False`):** Colapsa la numeración (`VAR1`, `VAR2`) a un único token `VAR` para tolerar reordenamientos. _Para mantener la capacidad de cumplir estrictamente con el mapeo uno-a-uno que sugiere la cátedra (VAR1, VAR2), se expone el flag opcional `--index-vars` en la CLI._

### 2.2. Normalización y Tabla de Símbolos

Se crea una tabla de símbolos por cada función para aislar su lógica de los nombres elegidos:

- **Firmas y recursión:** El nombre de la función y sus llamadas a sí misma mutan al token `FUNC`.
- **Variables locales:** Identificadores locales (parámetros, asignaciones, variables de `for`, `with...as`, `except...as`, `lambda` y comprensiones) se mapean a `VAR1, VAR2...` por orden de aparición. Nombres `global` o `nonlocal` se excluyen.
- **Aislamiento de ámbitos:** Un `ast.NodeVisitor` frena el descenso en definiciones internas (`FunctionDef`, `ClassDef`) para no mezclar variables de funciones anidadas.
- **Nombres libres:** Funciones externas (`print`) y alias de importación se conservan.

### 2.3. Simplificaciones estructurales

- **Atributos y métodos:** Se normaliza el objeto base si es local, pero el método se conserva (ej. `VAR1.append`) para distinguir semántica.
- **Literales y metadatos:** Números y strings pasan a `LIT`. Se conservan constantes estructurales (`None`, `True`, `False`, `...`). Se eliminan _docstrings_ y anotaciones de tipos (Type Hints).
- **Nodos de contexto:** Se omiten `Load`, `Store`, `Del`. Un identificador escrito o leído no aporta estructura algorítmica nueva y genera ruido en la comparación.

### 2.4. Extracción

Se capturan funciones estándar, asíncronas y métodos. Las funciones anidadas se extraen por separado guardando su nombre calificado (ej. `Clase.metodo`) y se diferencian por número de línea si hay nombres duplicados (ej. propiedades con `@setter`).

---

## 3. Métricas y calibración experimental (`lab/calibrate.py`)

Comparamos secuencias usando dos métricas sobre 9 pares de control (4 clones, 5 algoritmos distintos).

1.  **Jaccard sobre n-gramas ($n=3$):** Evalúa intersección sobre unión ($|A \cap B| / |A \cup B|$). Ideal para detectar fragmentos compartidos.
2.  **Levenshtein normalizada:** Mide inserciones, eliminaciones y sustituciones. Evalúa el orden global de la secuencia.

**Justificación de Hiperparámetros:**

- **Por qué `index_vars=False` por defecto:** Con `True`, reordenar sentencias independientes renumera variables y hunde el score Jaccard (n=3) a `0.451` (no detecta el clon). Con `False`, el clon sube a `0.867` y el margen de separación entre clones/no-clones mejora radicalmente de `0.288` a `0.447`.
- **Por qué $n=3$:** Trigramas ofrece el mejor equilibrio. $n=2$ genera falsos positivos por estructuras comunes genéricas; $n=4$ penaliza demasiado las inserciones pequeñas (ej. agregar un `print` en el medio).
- **Umbrales (`THRESHOLDS`):** Fijados empíricamente en **`0.50` para Jaccard** y **`0.72` para Levenshtein**, valores que separaron exitosamente los 9 casos de prueba.

---

## 4. Limitaciones conocidas

- **Clones semánticos:** Un bucle `for` reescrito como algoritmo recursivo altera el AST por completo y no será detectado, ya que el motor mide similitud sintáctica, no equivalencia matemática.
- **Compromiso de identidad de variables:** `index_vars=False` pierde la distinción matemática en expresiones (trata igual `a + a` que `a + b`). Activar `--index-vars` soluciona esto, pero pierde tolerancia al reordenamiento de líneas.
- **Simplificación de ámbitos:** Las variables de comprensiones y los parámetros de `lambda` se recolectan en la tabla de símbolos de la función contenedora. A nivel semántico en Python 3 estos generan sus propios sub-ámbitos, pero para el cálculo de similitud estructural a escala de función, esta simplificación mantiene la lógica contigua sin alterar significativamente los n-gramas.
- **Falsos positivos en funciones cortas:** Funciones triviales de 2 o 3 líneas (como _getters/setters_) comparten el mismo esqueleto de AST básico y superan el umbral fácilmente aunque no estén relacionadas. Por ejemplo, dos métodos getters distintos (`return self.name` vs `return self.age`) generan secuencias de apenas 6 tokens que difieren en uno solo. Esto genera un falso positivo superando el umbral de Levenshtein (0.83 > 0.72). Implementar un filtro de `MIN_TOKENS` mitiga este problema.
- **Dependencia de nombres externos:** Renombrar importaciones o funciones _built-in_ penaliza el score, ya que la herramienta no sabe si `limpiar()` y `normalizar()` hacen lo mismo.
- **Closures y Clases anidadas:** Las variables de un ámbito externo capturadas en una función interna conservan su nombre original. Asimismo, los atributos de clases definidas dentro de funciones no se normalizan, manteniéndose aislados.
