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

Para proyectar una estructura de árbol en una secuencia lineal comparable, el orden del recorrido es fundamental. Un recorrido en preorden (DFS) visita primero el nodo actual y luego sus hijos de izquierda a derecha (según el orden de campos `_fields` del AST). En cambio, `ast.walk()` no garantiza un orden específico de recorrido (en la práctica recorre el árbol por niveles, como se verificó en `lab/explore_ast.py`), por lo que no resulta adecuado cuando se requiere un orden reproducible en preorden. Por ello, se implementa un recorrido explícito mediante `ast.iter_child_nodes()`.

---

## 2. Decisiones de diseño

### 2.1. Recorrido estricto en preorden y formato de tokens

Para convertir los árboles en secuencias de tokens (`src/serializer.py`), implementamos un recorrido estricto en preorden basado en `ast.iter_child_nodes()`, descartando `ast.walk()`. Esto mantiene contiguos los componentes de cada subárbol según el orden determinista de los campos `_fields` del AST.

Cada nodo visitado emite un único token:

- **Nodos puramente estructurales** (`BinOp`, `Add`, `If`, `Return`, `Assign`): emiten únicamente el nombre de su tipo de nodo (`Tipo`).
- **Nodos con valor semántico o normalizado** (`Name`, `arg`, `Constant`, `Attribute`, `FunctionDef`, `ClassDef`, `keyword`, `alias`, `ImportFrom`, `ExceptHandler`, capturas `match`): emiten un token compuesto `Tipo:valor` (por ejemplo, `Name:VAR1`, `Constant:LIT`, `Attribute:append`, `ImportFrom:os`). En los nodos `ast.alias`, se emite el nombre del elemento importado (`alias:numpy`) omitiendo el alias local en la declaración, aunque las referencias posteriores al alias en el cuerpo se conservan como nombres libres.
- **Modo sin índice (`index_vars=False`):** El serializador incluye una opción para colapsar los subíndices de variables (`VAR1`, `VAR2` $\rightarrow$ `VAR`), permitiendo evaluar el impacto del reordenamiento de líneas independientes sobre la numeración de la tabla de símbolos.

### 2.2. Normalización mediante tabla de símbolos local

Para lograr que la comparación no dependa de los nombres que eligió el programador, se construye una tabla de símbolos independiente por cada ámbito de función:

- **Nombre de la función definida y recursión:** El nombre en la firma se reemplaza por el token neutro `FUNC`. Si la función realiza llamadas recursivas a sí misma, dichas referencias también se normalizan a `FUNC`.
- **Parámetros y variables locales:** Los identificadores ligados dentro de la función (parámetros, asignaciones, variables de `for`, `with ... as`, `except ... as`, capturas `match`, parámetros de `lambda` y comprensiones) se reemplazan por tokens genéricos (`VAR1`, `VAR2`, etc.) numerados determinísticamente según su orden de primera aparición en el recorrido del árbol (donde, por ejemplo, `targets` precede a `value` en una asignación). Los nombres declarados como `global` o `nonlocal` en ese ámbito se excluyen de la tabla local. Incluir las variables de comprensiones y `lambda` en la tabla de la función contenedora constituye una simplificación deliberada respecto a los sub-ámbitos implícitos de Python 3.
- **Aislamiento de ámbitos anidados:** La recolección de nombres ligados se implementa mediante un `ast.NodeVisitor` (`_BoundNameCollector`) que detiene el descenso al encontrar definiciones anidadas (`FunctionDef`, `AsyncFunctionDef`, `ClassDef`). De esta manera, el nombre de la función o clase interna queda registrado en el ámbito contenedor, pero sus parámetros, variables locales y declaraciones `global` o `nonlocal` se procesan en una tabla de símbolos independiente.
- **Nombres libres e importaciones:** Los nombres de funciones llamadas (`print`, `len`, helpers externos) y los alias de módulos importados (`import ... as ...`) se conservan sin cambios para no equiparar invocaciones a operaciones o dependencias distintas.

### 2.3. Tratamiento de atributos y métodos

En expresiones de acceso (como `obj.append(value)`), se va a normalizar el identificador del objeto base cuando corresponda a una variable local, pero se conservará explícitamente el nombre del método o atributo. Si normalizáramos los métodos, no podríamos diferenciar operaciones opuestas (como `lista.append` frente a `lista.remove`).

### 2.4. Simplificación de literales, documentación y tipos

- **Valores literales y constantes estructurales:** Los literales numéricos, cadenas de texto y bytes se reemplazan por el token genérico `LIT` (conservando la estructura interna en el caso de `f-strings`). Se preservan sin cambios las constantes singulares `None`, `True`, `False` y `...` (`Ellipsis`), dado que suelen desempeñar un rol de control de flujo o estructural (`if x is None`, `return False`).
- **Docstrings y Type Hints:** Se eliminan los _docstrings_ iniciales (insertando `Pass` si el cuerpo quedara vacío) y las anotaciones de tipos en parámetros, retornos y asignaciones (`AnnAssign` se transforma en `Assign` estándar, o en `Pass` si carece de valor asignado). Esta transformación prioriza la equivalencia estructural por sobre los metadatos declarativos de tipos.

### 2.5. Omisión de nodos de contexto

Inicialmente vamos a omitir los nodos estructurales que indican el contexto de una variable (`Load`, `Store`, `Del`). Su inclusión genera n-gramas triviales de alta frecuencia (como `Name, Load, Add`) presentes en casi cualquier función, lo que incrementa el solapamiento entre funciones no relacionadas.

### 2.6. Extracción de funciones y nombres calificados

El extractor va a capturar funciones estándar, asíncronas, métodos de clase y funciones anidadas. Una función anidada se extrae como función propia (`externa.interna`) y además permanece dentro del cuerpo de la función externa. Para evitar ambigüedades (por ejemplo, múltiples métodos `__init__` en un mismo archivo), el sistema guardará la ruta relativa del archivo y el nombre calificado (`Clase.metodo`).

La construcción de nombres calificados se resuelve mediante un `ast.NodeVisitor` que mantiene una pila de ámbitos activos (`scope`) al entrar y salir de nodos `ClassDef`, `FunctionDef` y `AsyncFunctionDef`. Las expresiones `ast.Lambda` se excluyen de la extracción independiente dado que son expresiones anónimas y no definiciones de funciones. En caso de existir múltiples definiciones con el mismo nombre calificado en un mismo archivo (por ejemplo, propiedades con `@setter`), se diferenciarán por su número de línea (`lineno`).

---

## 3. Métricas de similitud

Para comparar las secuencias de tokens vamos a utilizar dos métricas complementarias:

1. **Índice de Jaccard sobre n-gramas:** Compara la intersección y la unión de los conjuntos de n-gramas de dos secuencias. Puede tolerar determinados cambios de orden de bloques independientes (clones de Tipo 3), aunque su comportamiento depende del tamaño de los n-gramas y de las estructuras comparadas.
2. **Distancia de Levenshtein normalizada:** Considera las inserciones, eliminaciones y sustituciones necesarias para transformar una secuencia en otra. Permite evaluar diferencias de contenido y orden, aunque puede penalizar cambios estructurales que no alteran el comportamiento del programa.

La combinación de ambas métricas, el tamaño de los n-gramas y el umbral de corte para definir cuándo dos funciones son candidatas a duplicado se evaluarán experimentalmente mediante casos de prueba.

## 4. Limitaciones conocidas

- **Equivalencia semántica vs. estructural:** Dos funciones que resuelven el mismo problema mediante algoritmos distintos (ej. recursividad vs. iteración) van a tener estructuras diferentes y obtendrán un puntaje bajo (clones de Tipo 4).
- **Sensibilidad de la numeración `VARn` al reordenamiento:** Como los identificadores `VAR1`, `VAR2`, ... se asignan por orden de primera aparición, reordenar sentencias independientes que introducen variables nuevas puede permutar sus índices (`VAR3` $\leftrightarrow$ `VAR4`), reduciendo parcialmente el solapamiento de n-gramas.
- **Sensibilidad de nombres libres, _closures_ e imports:** Como decidimos preservar los nombres libres y los alias de importación, si dos funciones clonadas llaman a funciones auxiliares o alias con nombres distintos, o si una función anidada captura variables de su función envolvente (_closures_) con nombres distintos, el motor penalizará su puntaje. Asimismo, si una función se define con el mismo nombre que un _built-in_ (ej. `def sum(...)`) e invoca dicho _built-in_ dentro de su cuerpo, la llamada se interpretará como recursiva (`FUNC`).
- **Decoradores conservados:** Los decoradores de la función (`decorator_list`) se preservan en el árbol normalizado, por lo que diferencias en decoradores afectan la similitud estructural.
- **Falsos positivos por simplicidad:** Las funciones demasiado cortas o triviales (ej. simples _getters/setters_) suelen compartir el mismo esqueleto AST, por lo que podrían superar el umbral de similitud aunque no estén relacionadas conceptualmente.
