# Notas de diseño y arquitectura

Este documento detalla los fundamentos teóricos, los análisis del entorno y las decisiones arquitectónicas que guían el desarrollo del motor de búsqueda de similitud de funciones Python.

## 1. Fundamentos teóricos y características de Python

### 1.1. AST y gramáticas independientes del contexto

El módulo `ast` de Python permite convertir el código fuente en un Árbol de Sintaxis Abstracta (_Abstract Syntax Tree_, AST). A diferencia de un árbol de derivación concreto (que representa cada regla gramatical aplicada e incluye tokens puramente de formato como paréntesis o dos puntos), el AST ofrece una representación abstracta de la estructura sintáctica del programa, omitiendo detalles de la escritura concreta.

Desde el punto de vista formal, el AST se relaciona directamente con las estructuras arbóreas del análisis sintáctico de gramáticas independientes del contexto (Tipo 2 en la jerarquía de Chomsky), aunque desde Python 3.9 el intérprete utiliza un analizador basado en gramáticas PEG y resuelve la indentación en la etapa léxica.

### 1.2. Ámbitos y tabla de símbolos

En la teoría de compiladores, una tabla de símbolos es la estructura que usa el analizador para guardar información sobre los identificadores (variables, funciones, clases) y sus respectivos ámbitos de declaración y uso.

En Python, los identificadores pueden estar "ligados" al ámbito local de una función (como parámetros, variables asignadas, variables de control en bucles `for`, manejadores `with`/`except` y comprensiones) o ser "libres" (como llamadas a funciones _built-in_ o referencias externas). Diferenciar el origen de un identificador es clave para no alterar la estructura lógica del programa al normalizarlo.

### 1.3. Orden estructural y recorridos de árboles

Para proyectar una estructura de árbol en una secuencia lineal comparable, el orden del recorrido debe ser consistente. Un recorrido en preorden (DFS) visita primero el nodo actual y luego sus hijos de izquierda a derecha, manteniendo contiguos los componentes de cada subárbol. En cambio, recorridos como `ast.walk()` no garantizan ese orden en preorden, por lo que no resultan adecuados para construir directamente la secuencia de tokens.

---

## 2. Decisiones de diseño

### 2.1. Recorrido estricto en preorden

Para convertir los árboles en secuencias de tokens, vamos a implementar un recorrido explícito en preorden basado en `ast.iter_child_nodes()` / `ast.NodeVisitor`, descartando `ast.walk()`. Esto garantiza una secuencia reproducible que conserva el orden estructural elegido para la comparación.

### 2.2. Normalización mediante tabla de símbolos local

Para lograr que la comparación no dependa de los nombres que eligió el programador, vamos a armar una tabla de símbolos local al procesar cada función:

- **Nombre de la función definida:** Se descarta y reemplaza por un identificador neutro para que no influya en la comparación.
- **Parámetros y variables locales:** Los identificadores ligados al ámbito local (parámetros, asignaciones, variables de `for`, `with`, `except` y comprensiones) se van a reemplazar por tokens genéricos (`VAR1`, `VAR2`, etc.), manteniendo la correspondencia cada vez que aparezcan. La identificación considerará las reglas de ámbito de Python, incluyendo funciones anidadas y declaraciones `global` o `nonlocal`.
- **Nombres libres y funciones invocadas:** Los nombres de funciones llamadas (`print`, `len`, helpers externos) e identificadores libres se van a conservar tal cual para no equiparar invocaciones a operaciones distintas.

### 2.3. Tratamiento de atributos y métodos

En expresiones de acceso (como `obj.append(value)`), se va a normalizar el identificador del objeto base cuando sea local, pero se conservará explícitamente el nombre del método o atributo. Si normalizáramos los métodos, no podríamos diferenciar operaciones opuestas (como `lista.append` frente a `lista.remove`).

### 2.4. Simplificación de literales, documentación y tipos

- **Valores literales:** Se van a reemplazar por un token genérico (`LIT`). De esta forma, la comparación se centra en la estructura algorítmica y no en los datos constantes.
- **Docstrings y Type Hints:** Se van a eliminar antes de serializar el árbol. Python procesa un _docstring_ como un nodo literal al inicio de la función; si no lo sacamos, generaría diferencias falsas al comparar la misma función con y sin comentarios.

### 2.5. Omisión de nodos de contexto

Inicialmente vamos a omitir los nodos que indican el contexto de uso de una variable (`Load`, `Store`, `Del`). Incluirlos genera n-gramas triviales de alta frecuencia (presentes en casi cualquier función), lo que incrementa el solapamiento entre funciones no relacionadas.

### 2.6. Extracción de funciones y nombres calificados

El extractor captura funciones estándar, asíncronas, métodos de clase y funciones anidadas. Una función anidada se extrae como función propia (`externa.interna`) y además permanece dentro del cuerpo de la función contenedora. Para evitar ambigüedades, se guarda la ruta relativa del archivo y el nombre calificado (`Clase.metodo`).

La construcción de nombres calificados se resuelve mediante un `ast.NodeVisitor` que mantiene una pila de ámbitos activos (`scope`) al entrar y salir de nodos `ClassDef`, `FunctionDef` y `AsyncFunctionDef`. Las expresiones `ast.Lambda` se excluyen dado que son expresiones anónimas y no definiciones de funciones. En caso de existir múltiples definiciones con el mismo nombre calificado en un mismo archivo (por ejemplo, propiedades con `@setter`), se diferenciarán por su número de línea (`lineno`).

---

## 3. Métricas de similitud

Para comparar las secuencias de tokens vamos a evaluar dos métricas complementarias:

1. **Índice de Jaccard sobre n-gramas:** Compara la intersección y la unión de los conjuntos de n-gramas de dos secuencias. Puede tolerar determinados cambios de orden de bloques independientes (clones de Tipo 3), dependiendo del tamaño de los n-gramas y de las estructuras comparadas.
2. **Distancia de Levenshtein normalizada:** Considera las inserciones, eliminaciones y sustituciones necesarias para transformar una secuencia en otra. Evalúa diferencias tanto de contenido como de orden global.

Los parámetros y el umbral de corte para definir cuándo dos funciones son candidatas a duplicado se calibrarán experimentalmente mediante casos de prueba.

## 4. Limitaciones conocidas

- **Equivalencia semántica vs. estructural:** Dos funciones que resuelven el mismo problema mediante algoritmos distintos (ej. recursividad vs. un bucle `for`) tendrán estructuras diferentes y obtendrán un puntaje bajo (clones de Tipo 4).
- **Sensibilidad de la normalización:** Preservar los nombres libres implica que si dos funciones clonadas llaman a funciones auxiliares externas con nombres distintos, el motor reducirá su puntaje de similitud.
- **Falsos positivos por simplicidad:** Funciones demasiado cortas o triviales (ej. simples _getters/setters_) suelen compartir el mismo esqueleto AST, pudiendo superar el umbral de similitud aunque no estén relacionadas conceptualmente.
