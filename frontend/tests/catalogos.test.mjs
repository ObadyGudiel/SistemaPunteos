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
