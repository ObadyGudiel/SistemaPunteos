import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

test("el inicio de sesión solicita el carnet", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");

  assert.match(
    html,
    /<input type="text" id="usuarioLogin" placeholder="Ingrese su carnet" \/>/,
  );
});

test("el inicio de sesión muestra los logotipos sin el panel informativo", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
  const login = html.match(/<div id="loginView"[\s\S]*?<div id="appView"/)?.[0] ?? "";

  assert.doesNotMatch(login, /class="hero-card card"/);
  assert.match(login, /class="login-brand-marks"/);
  assert.match(login, /src="img\/logo-san-luis\.png/);
  assert.match(login, /src="img\/logo-diversificado\.png/);
});

test("los paneles muestran únicamente el nombre de cada rol", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");

  assert.match(html, /id="panelDirector"[\s\S]*?<h2>Director<\/h2>/);
  assert.match(html, /id="panelDocente"[\s\S]*?<h2>Docente<\/h2>/);
  assert.match(html, /id="panelEstudiante"[\s\S]*?<h2>Estudiante<\/h2>/);
});

test("el encabezado se desplaza junto con la página", async () => {
  const css = await readFile(new URL("../css/styles.css", import.meta.url), "utf8");
  const topbar = css.match(/\.topbar \{[\s\S]*?\n\}/)?.[0] ?? "";

  assert.doesNotMatch(topbar, /position:\s*(sticky|fixed)/);
});

test("en computadora se oculta el título reservado para el menú móvil", async () => {
  const css = await readFile(new URL("../css/styles.css", import.meta.url), "utf8");

  assert.match(css, /\.topbar \.mobile-topbar-title\s*\{\s*display:\s*none;/);
});

test("en teléfono se oculta la tarjeta duplicada de navegación", async () => {
  const css = await readFile(new URL("../css/styles.css", import.meta.url), "utf8");
  const estilosMoviles = css.slice(css.indexOf("@media (max-width: 680px)"));

  assert.match(estilosMoviles, /\.panel-shell\s*\{\s*display:\s*none;/);
  assert.match(estilosMoviles, /\.student-hero\s*\{\s*display:\s*none;/);
});

test("el menú móvil del director contiene sus accesos principales", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
  const funcion = html.match(
    /function obtenerOpcionesMenuMovil\(rol\) \{[\s\S]*?\r?\n    \}(?=\r?\n\r?\n    function actualizarMenuMovil)/,
  )?.[0];

  assert.ok(funcion, "No se encontró la función del menú móvil");

  const contexto = {};
  vm.createContext(contexto);
  vm.runInContext(funcion, contexto);

  assert.deepEqual(
    JSON.parse(JSON.stringify(contexto.obtenerOpcionesMenuMovil("director"))),
    [
      { etiqueta: "Inicio", seccion: "punteos" },
      { etiqueta: "Docentes", seccion: "docentes" },
      { etiqueta: "Estudiantes", seccion: "estudiantes" },
      { etiqueta: "Cursos", seccion: "cursos" },
      { etiqueta: "Asistencia", seccion: "asistencia" },
    ],
  );
});

test("el menú móvil de docente inicia en Inicio y el estudiante no tiene acceso duplicado", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
  const funcion = html.match(
    /function obtenerOpcionesMenuMovil\(rol\) \{[\s\S]*?\r?\n    \}(?=\r?\n\r?\n    function actualizarMenuMovil)/,
  )?.[0];

  assert.ok(funcion, "No se encontró la función del menú móvil");

  const contexto = {};
  vm.createContext(contexto);
  vm.runInContext(funcion, contexto);

  assert.equal(contexto.obtenerOpcionesMenuMovil("docente")[0].etiqueta, "Inicio");
  assert.deepEqual(JSON.parse(JSON.stringify(contexto.obtenerOpcionesMenuMovil("estudiante"))), []);
  assert.match(html, /id="docVer"[\s\S]*?<h2>Registro de punteos<\/h2>/);
});

test("el menú móvil tiene flecha de cierre y salida junto a las opciones", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
  const css = await readFile(new URL("../css/styles.css", import.meta.url), "utf8");
  const estilosMoviles = css.slice(css.indexOf("@media (max-width: 680px)"));

  assert.match(html, /class="mobile-menu-close"[\s\S]*?aria-label="Cerrar menú"[\s\S]*?onclick="cerrarMenuMovil\(\)"/);
  assert.match(estilosMoviles, /\.mobile-menu-close\s*\{/);
  assert.doesNotMatch(estilosMoviles, /\.mobile-menu-logout\s*\{\s*width:\s*100%;\s*margin-top:\s*auto;/);
});

test("el detalle del primer alumno se abre hacia abajo", async () => {
  const css = await readFile(new URL("../css/styles.css", import.meta.url), "utf8");

  assert.match(css, /tbody tr:first-child \.score-detail\s*\{[\s\S]*?top:\s*calc\(100% \+ 10px\);/);
  assert.match(css, /tbody tr:first-child \.score-detail\s*\{[\s\S]*?bottom:\s*auto;/);
});

test("el Director puede iniciar el restablecimiento secuencial de estudiantes", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
  const funcion = html.match(
    /async function restablecerPasswordsEstudiantes\(\) \{[\s\S]*?\r?\n    \}(?=\r?\n\r?\n    async function cargarEstudiantesDirector)/,
  )?.[0];

  assert.ok(funcion, "No se encontró el restablecimiento de contraseñas estudiantiles");

  const solicitudes = [];
  const mensajes = [];
  const contexto = {
    confirm: () => true,
    api: async (ruta, opciones) => {
      solicitudes.push([ruta, opciones]);
      return { estudiantes: 3 };
    },
    mostrarMensaje: (...mensaje) => mensajes.push(mensaje),
    cargarEstudiantesDirector: async () => {},
  };
  vm.createContext(contexto);
  vm.runInContext(funcion, contexto);
  await contexto.restablecerPasswordsEstudiantes();

  assert.deepEqual(
    JSON.parse(JSON.stringify(solicitudes)),
    [["/director/estudiantes/restablecer-passwords", { method: "POST" }]],
  );
  assert.equal(mensajes[0][0], "mensajeEstudiantesDir");
  assert.equal(mensajes[0][2], "success");
});

test("la tabla de estudiantes muestra la contraseña junto al carnet", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
  const funcion = html.match(
    /async function cargarEstudiantesDirector\(\) \{[\s\S]*?\r?\n    \}(?=\r?\n\r?\n    async function crearEstudiante)/,
  )?.[0];

  assert.match(html, /<tr><th>Carnet<\/th><th>Contraseña<\/th><th>Nombre<\/th>/);
  assert.match(
    funcion ?? "",
    /<td>\$\{escapar\(row\.codigo_carnet\)\}<\/td>\s*<td><code>\$\{escapar\(row\.password_temporal \|\| ""\)\}<\/code><\/td>/,
  );
});

test("el menú móvil del estudiante muestra sus datos académicos", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
  const funcion = html.match(
    /function actualizarDatosEstudianteMenuMovil\(data\) \{[\s\S]*?\r?\n    \}(?=\r?\n\r?\n    async function cargarDatosEstudiante)/,
  )?.[0];

  assert.ok(funcion, "No se encontró la función para mostrar los datos del estudiante en el menú móvil");

  const elementos = new Map(
    ["menuEstCodigo", "menuEstNombre", "menuEstCarrera", "menuEstGrado", "menuEstCiclo"].map(id => [id, { textContent: "" }]),
  );
  const contexto = { document: { getElementById: id => elementos.get(id) } };
  vm.createContext(contexto);
  vm.runInContext(funcion, contexto);
  contexto.actualizarDatosEstudianteMenuMovil({
    codigo_carnet: "F654UWE",
    apellidos: "LÓPEZ TICÚN",
    nombres: "WILSON GEOVANNY",
    carrera: "Perito en Electrónica y Dispositivos",
    grado: "Quinto",
    ciclo_escolar: 2026,
  });

  assert.deepEqual(
    [...elementos.values()].map(elemento => elemento.textContent),
    ["F654UWE", "LÓPEZ TICÚN, WILSON GEOVANNY", "Perito en Electrónica y Dispositivos", "Quinto", "2026"],
  );
});

test("el estudiante carga sus punteos sin mensajes de estado redundantes", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
  const funcion = html.match(
    /async function cargarDatosEstudiante\(codigoCarnet\) \{[\s\S]*?\r?\n    \}(?=\r?\n\r?\n    function mostrarMensaje)/,
  )?.[0];

  assert.ok(funcion, "No se encontró la carga de punteos del estudiante");

  const mensajes = [];
  const elementos = new Map([
    ["estCodigo", { textContent: "" }],
    ["estNombre", { textContent: "" }],
    ["estCarrera", { textContent: "" }],
    ["estGrado", { textContent: "" }],
    ["estCiclo", { textContent: "" }],
    ["tablaEstudiante", { innerHTML: "", appendChild() {} }],
  ]);
  const contexto = {
    api: async () => ({
      codigo_carnet: "F654UWE",
      apellidos: "LÓPEZ TICÚN",
      nombres: "WILSON GEOVANNY",
      carrera: "Electrónica",
      grado: "Quinto",
      ciclo_escolar: 2026,
      cursos: [{ curso: "Matemática", bimestre_1: 80, bimestre_2: 80, bimestre_3: 80, bimestre_4: 80, promedio_final: 80, estado: "Aprobado" }],
    }),
    actualizarDatosEstudianteMenuMovil() {},
    crearPunteoConDetalle: () => ({}),
    mostrarMensaje: (...mensaje) => mensajes.push(mensaje),
    formato: valor => String(valor),
    escapar: valor => String(valor),
    document: {
      getElementById: id => elementos.get(id),
      createElement: () => ({}),
    },
  };
  vm.createContext(contexto);
  vm.runInContext(funcion, contexto);
  await contexto.cargarDatosEstudiante("F654UWE");

  assert.deepEqual(mensajes, []);
});

class OpcionFalsa {
  constructor() {
    this.value = "";
    this.textContent = "";
  }
}

function crearSelect() {
  return {
    options: [],
    innerHTML: "",
    appendChild(opcion) {
      this.options.push(opcion);
    },
  };
}

test("cargarCatalogos llena los bimestres de ingreso e importación", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
  const cargarCatalogos = html.match(
    /async function cargarCatalogos\(\) \{[\s\S]*?\r?\n    \}(?=\r?\n\r?\n    function llenarSelect\()/,
  )?.[0];
  const llenarSelect = html.match(
    /function llenarSelect\(id, datos, campo, textoInicial\) \{[\s\S]*?\r?\n    \}(?=\r?\n\r?\n    function llenarSelectDocentes)/,
  )?.[0];
  const codigo = [cargarCatalogos, llenarSelect].filter(Boolean).join("\n");

  assert.ok(codigo, "No se encontraron las funciones de catálogos");

  const selectores = new Map([
    ["insBimestre", crearSelect()],
    ["impBimestre", crearSelect()],
  ]);
  const contexto = {
    api: async () => ({
      carreras: [],
      grados: [],
      cursos: [],
      bimestres: [
        { nombre: "Primer Bimestre" },
        { nombre: "Segundo Bimestre" },
        { nombre: "Tercer Bimestre" },
        { nombre: "Cuarto Bimestre" },
      ],
      ciclos: [],
      docentes: [],
    }),
    catalogosCargados: false,
    llenarSelectDocentes: () => {},
    document: {
      createElement: () => new OpcionFalsa(),
      getElementById: (id) => selectores.get(id) ?? null,
    },
  };

  vm.createContext(contexto);
  vm.runInContext(codigo, contexto);
  await contexto.cargarCatalogos();

  for (const id of ["insBimestre", "impBimestre"]) {
    assert.deepEqual(
      selectores.get(id).options.map((opcion) => opcion.textContent),
      [
        "Seleccione bimestre",
        "Primer Bimestre",
        "Segundo Bimestre",
        "Tercer Bimestre",
        "Cuarto Bimestre",
      ],
    );
  }
});
