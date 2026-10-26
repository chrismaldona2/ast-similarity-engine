# Notas de diseño y arquitectura

Este documento detalla los fundamentos teóricos, los análisis del entorno y las decisiones arquitectónicas que guían el desarrollo del motor de búsqueda de similitud de funciones Python.

## 1. Fundamentos teóricos y características de Python

### 1.1. AST y gramáticas independientes del contexto

El módulo `ast` de Python permite convertir el código fuente en un Árbol de Sintaxis Abstracta (_Abstract Syntax Tree_, AST). A diferencia de un árbol de derivación concreto —que representa las reglas gramaticales aplicadas y sus símbolos intermedios o de formato como paréntesis y dos puntos—, el AST ofrece una representación abstracta de la estructura sintáctica del programa, omitiendo detalles de la escritura concreta.

Desde el punto de vista formal, el AST puede relacionarse con las estructuras arbóreas del análisis sintáctico basado en gramáticas independientes del contexto (Tipo 2 en la jerarquía de Chomsky). Como precisión técnica, cabe notar que desde Python 3.9 el intérprete utiliza un analizador basado en gramáticas PEG y resuelve la indentación en la etapa léxica mediante tokens `INDENT`/`DEDENT`, por lo que la correspondencia con una GIC de Tipo 2 es una aproximación conceptual.

### 1.2. Ámbitos y tabla de símbolos

En la teoría de compiladores, una tabla de símbolos es la estructura que usa el analizador para guardar información sobre los identificadores (variables, funciones, clases) y sus respectivos ámbitos de declaración y uso.

En Python, los identificadores pueden estar "ligados" al ámbito local de una función (como parámetros, asignaciones, variables de control en `for`, manejadores `with ... as`, `except ... as` y comprensiones) o ser "libres" (como llamadas a funciones _built-in_ o variables externas). Diferenciar el origen de un identificador es clave para no alterar la estructura lógica del programa al normalizarlo.

### 1.3. Orden estructural y recorridos de árboles

Para proyectar una estructura de árbol en una secuencia lineal comparable, el orden del recorrido es fundamental. Un recorrido en preorden (DFS) visita primero el nodo actual y luego sus hijos de izquierda a derecha, según el orden de los campos del AST. En cambio, `ast.walk()` no garantiza un orden específico de recorrido, por lo que no resulta adecuado para construir directamente una secuencia de tokens cuando se requiere un orden reproducible en preorden. Por este motivo, se implementa un recorrido explícito mediante `ast.iter_child_nodes()`, que visita cada nodo antes que sus hijos y conserva el orden en que estos aparecen en la estructura del AST.

---

## 2. Decisiones de diseño

### 2.1. Recorrido estricto en preorden y formato de tokens

Para convertir los árboles en secuencias de tokens (`src/serializer.py`), se implementa un recorrido estricto en preorden basado en `ast.iter_child_nodes()`, descartando `ast.walk()`. Esto mantiene contiguos los componentes de cada subárbol según el orden de sus campos en el AST.

Cada nodo visitado emite un único token:

- **Nodos puramente estructurales** (`BinOp`, `Add`, `If`, `Return`, `Assign`): emiten únicamente el nombre de su tipo de nodo (`Tipo`).
- **Nodos que incluyen un valor relevante** (`Name`, `arg`, `Constant`, `Attribute`, `FunctionDef`, `ClassDef`, `keyword`, `alias`, `ExceptHandler` y nodos de captura de patrones `match`): emiten un token compuesto `Tipo:valor`, por ejemplo, `Name:VAR`, `Constant:LIT` o `Attribute:append`.
- **Importaciones:** los nodos `ast.ImportFrom` emiten únicamente el tipo `ImportFrom`, ya que el serializador no incorpora su módulo de origen como valor del token. En los nodos `ast.alias`, se emite el nombre del elemento importado, por ejemplo, `alias:numpy`. El alias local de la declaración no se incluye en ese token, aunque las referencias posteriores a dicho alias en el cuerpo se conservan como nombres.
- **Modo sin índice (`index_vars=False`):** el serializador incluye una opción para colapsar los subíndices de variables (`VAR1`, `VAR2`, etc.) en un único token `VAR`. Esto reduce la sensibilidad a la numeración de variables, aunque no elimina la sensibilidad al orden de las sentencias en la secuencia serializada.

### 2.2. Normalización mediante tabla de símbolos local

Para lograr que la comparación no dependa de los nombres que eligió el programador, se construye una tabla de símbolos independiente por cada ámbito de función:

- **Nombre de la función definida y recursión:** El nombre en la firma se reemplaza por el token neutro `FUNC`. Si la función realiza llamadas recursivas a sí misma, dichas referencias también se normalizan a `FUNC`.
- **Parámetros y variables locales:** Los identificadores ligados dentro de la función (parámetros, asignaciones, variables de `for`, `with ... as`, `except ... as`, capturas `match`, parámetros de `lambda` y comprensiones) se reemplazan por tokens genéricos (`VAR1`, `VAR2`, etc.) numerados determinísticamente según su orden de primera aparición en el recorrido del árbol (donde, por ejemplo, `targets` precede a `value` en una asignación). Los nombres declarados como `global` o `nonlocal` en ese ámbito se excluyen de la tabla local. Incluir las variables de comprensiones y `lambda` en la tabla de la función contenedora constituye una simplificación deliberada respecto a los sub-ámbitos implícitos de Python 3.
- **Aislamiento de ámbitos anidados:** La recolección de nombres ligados se implementa mediante un `ast.NodeVisitor` (`_BoundNameCollector`) que detiene el descenso al encontrar definiciones anidadas (`FunctionDef`, `AsyncFunctionDef`, `ClassDef`). De esta manera, el nombre de la función o clase interna queda registrado en el ámbito contenedor, pero sus parámetros, variables locales y declaraciones `global` o `nonlocal` se procesan en una tabla de símbolos independiente.
- **Nombres libres e importaciones:** Los nombres de funciones llamadas (`print`, `len`, helpers externos) y los alias de módulos importados (`import ... as ...`) se conservan sin cambios para no equiparar invocaciones a operaciones o dependencias distintas.

### 2.3. Tratamiento de atributos y métodos

En expresiones de acceso (como `obj.append(value)`), se normaliza el identificador del objeto base cuando corresponde a una variable local, pero se conserva explícitamente el nombre del método o atributo. Si se normalizaran los métodos, no podrían diferenciarse operaciones opuestas (como `lista.append` frente a `lista.remove`).

### 2.4. Simplificación de literales, documentación y tipos

- **Valores literales y constantes estructurales:** Los literales numéricos, cadenas de texto y bytes se reemplazan por el token genérico `LIT` (conservando la estructura interna en el caso de `f-strings`). Se preservan sin cambios las constantes singulares `None`, `True`, `False` y `...` (`Ellipsis`), dado que suelen desempeñar un rol de control de flujo o estructural (`if x is None`, `return False`).
- **Docstrings y Type Hints:** Se eliminan los _docstrings_ iniciales (insertando `Pass` si el cuerpo quedara vacío) y las anotaciones de tipos en parámetros, retornos y asignaciones (`AnnAssign` se transforma en `Assign` estándar, o en `Pass` si carece de valor asignado). Esta transformación prioriza la equivalencia estructural por sobre los metadatos declarativos de tipos.

### 2.5. Omisión de nodos de contexto

Se omiten los nodos que representan el contexto de acceso a una variable (`Load`, `Store`, `Del`). Estos nodos indican si un identificador se lee, se asigna o se elimina, pero no aportan directamente el nombre de la operación ni la estructura principal que interesa comparar. Omitirlos simplifica las secuencias y evita introducir diferencias relacionadas exclusivamente con el contexto de acceso. Por ejemplo, una variable utilizada como operando y otra utilizada como destino de una asignación no generan tokens adicionales únicamente por sus respectivos contextos de acceso.

### 2.6. Extracción de funciones y nombres calificados

El extractor captura funciones estándar, asíncronas, métodos de clase y funciones anidadas. Una función anidada se extrae como función propia (`externa.interna`) y además permanece dentro del cuerpo de la función externa. Para evitar ambigüedades (por ejemplo, múltiples métodos `__init__` en un mismo archivo), el sistema guarda la ruta relativa del archivo y el nombre calificado (`Clase.metodo`).

La construcción de nombres calificados se resuelve mediante un `ast.NodeVisitor` que mantiene una pila de ámbitos activos (`scope`) al entrar y salir de nodos `ClassDef`, `FunctionDef` y `AsyncFunctionDef`. Las expresiones `ast.Lambda` se excluyen de la extracción independiente dado que son expresiones anónimas y no definiciones de funciones. En caso de existir múltiples definiciones con el mismo nombre calificado en un mismo archivo (por ejemplo, propiedades con `@setter`), se diferencian por su número de línea (`lineno`).

---

### 3. Métricas de similitud y calibración experimental

Para comparar las secuencias de tokens se implementan dos métricas complementarias en `src/similarity.py`:

1. **Índice de Jaccard sobre conjuntos de n-gramas:** compara la intersección y la unión de los conjuntos de n-gramas contiguos de dos secuencias ($|A \cap B| / |A \cup B|$). Cuando una secuencia no vacía tiene menos de $n$ tokens, se la representa como un único tuplo con la secuencia completa para permitir su comparación sin descartarla. Como trabaja sobre conjuntos (`set`), no contabiliza la frecuencia de repetición de un mismo n-grama; una variante basada en multiconjuntos o `Counter` queda planteada como mejora futura.
2. **Distancia de Levenshtein normalizada:** calcula el mínimo de inserciones, eliminaciones y sustituciones de tokens mediante programación dinámica, con memoria $O(\min(|A|, |B|))$, y normaliza el resultado como $1 - d(A, B) / \max(|A|, |B|)$. Evalúa diferencias tanto de contenido como de orden global.

#### Calibración de hiperparámetros (`lab/calibrate.py`)

Se evaluaron nueve pares de control: cuatro clones positivos con variables renombradas, sentencias independientes reordenadas o líneas adicionales, y cinco pares negativos con distinta lógica algorítmica. Se variaron el tamaño del n-grama, $n \in \{2,3,4\}$, y el modo de indexación `index_vars`.

- **Elección de `index_vars=False` como configuración predeterminada del motor:** con `index_vars=True` (`VAR1`, `VAR2`, etc.), reordenar asignaciones independientes altera el orden de primera aparición de las variables y reduce el puntaje de Jaccard con $n=3$ de `0.867` a `0.451`. Al colapsar los subíndices en `VAR` (`index_vars=False`), se recupera tolerancia a ese reordenamiento: el clon obtiene `0.867` con Jaccard y `0.846` con Levenshtein. En estos pares de control, Jaccard presenta un mayor margen de separación entre clones y no-clones (`0.447`) que Levenshtein (`0.119`).

- **Elección del tamaño de n-grama ($n=3$):** con $n=2$, los pares negativos alcanzan una similitud máxima de `0.400`, con un margen de separación de `0.359`. Con $n=4$, el margen aumenta a `0.464`, pero los clones con una sentencia adicional pueden caer a `0.581`, haciéndose más sensibles a pequeñas inserciones. Con $n=3$, se obtiene un equilibrio entre tolerancia a cambios estructurales y discriminación: el margen es `0.447`, el puntaje del clon positivo menos similar es `0.667` y el puntaje del no-clon más similar es `0.220`.

- **Umbrales diferenciados por métrica (`THRESHOLDS`):** Levenshtein produce puntajes más altos para algunos pares no relacionados: el máximo observado es `0.655`, frente a `0.220` con Jaccard. Por ello se establecen umbrales predeterminados independientes: **`0.50` para Jaccard ($n=3$) y `0.72` para Levenshtein**. En el conjunto de control evaluado con `index_vars=False`, ambos umbrales separan correctamente los nueve pares: el mayor puntaje negativo queda por debajo del umbral y el menor puntaje positivo, por encima. Estos valores provienen de un conjunto pequeño de ejemplos construidos manualmente; constituyen una calibración empírica inicial y no garantizan la misma separación en cualquier corpus.

### 4. Limitaciones conocidas

- **Equivalencia semántica frente a estructural:** dos funciones que resuelven el mismo problema mediante algoritmos distintos (por ejemplo, recursividad e iteración) pueden presentar estructuras diferentes y obtener un puntaje bajo.
- **Compromiso de identidad de variables (`index_vars=False` frente a `True`):** en el modo predeterminado `index_vars=False`, las variables locales se representan con el mismo token `VAR`. Esto tolera mejor el reordenamiento de sentencias, pero pierde la distinción entre variables diferentes dentro de una expresión: por ejemplo, `a + a` y `a + b` pueden generar la misma secuencia. Con `index_vars=True`, la numeración `VARn` puede volverse sensible al orden de las sentencias.
- **Simplificación de ámbitos:** las variables de comprensiones y los parámetros de `lambda` se tratan como parte del ámbito de la función contenedora, aunque Python tiene reglas de ámbito específicas para estas construcciones. Además, el tratamiento de los ámbitos de clase no está completamente aislado del de la función envolvente. Estas simplificaciones pueden afectar la normalización de programas más complejos.
- **Nombres libres, cierres e importaciones:** al conservar los nombres libres y los alias de importación en sus usos dentro del cuerpo, dos funciones estructuralmente similares que llaman a funciones auxiliares o alias con nombres diferentes pueden obtener un puntaje menor. Lo mismo puede ocurrir si una función anidada captura variables de su función envolvente (_closures_) con nombres distintos.
- **Detección de recursión:** si una función se define con el mismo nombre que un _built-in_ (por ejemplo, `sum`) e invoca dicho nombre dentro de su cuerpo, el normalizador puede interpretar esa referencia como recursiva y reemplazarla por `FUNC`.
- **Decoradores conservados:** los decoradores de la función (`decorator_list`) se preservan en el árbol normalizado, por lo que sus diferencias afectan la similitud estructural.
- **Falsos positivos por simplicidad:** las funciones demasiado cortas o triviales, como algunos _getters_ y _setters_, pueden compartir el mismo esqueleto AST y superar el umbral aunque no estén relacionadas conceptualmente.
