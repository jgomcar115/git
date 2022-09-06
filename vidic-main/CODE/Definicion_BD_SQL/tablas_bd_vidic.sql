-- Suponiendo que está creada la base de datos (CREATE DATABASE vidic):

CREATE TABLE instalacion (
    id             SERIAL NOT NULL PRIMARY KEY,
		nombre         TEXT NOT NULL,
		ubicacion      TEXT
);

CREATE TABLE dispositivo (
    id             SERIAL NOT NULL PRIMARY key,
		instalacion_id INTEGER NOT NULL,
    nombre         TEXT NOT NULL,
    descripcion    TEXT,
    tipo           TEXT,
    opciones       TEXT,
    habilitado     BOOLEAN DEFAULT (True),
		FOREIGN KEY (instalacion_id) REFERENCES instalacion (id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE variables_dispositivo (
    id             SERIAL NOT NULL PRIMARY KEY,
    dispositivo_id INTEGER NOT NULL,
    nombre         TEXT NOT NULL,
    descripcion    TEXT,
    tipo           TEXT NOT NULL,
    unidades       TEXT,
    decimales      INTEGER,
    opciones       TEXT,
    historico      BOOLEAN DEFAULT (true),
    tiempo_real    BOOLEAN DEFAULT (true),
    FOREIGN KEY (dispositivo_id) REFERENCES dispositivo (id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE usuario (
    id             SERIAL NOT NULL PRIMARY KEY,
		nombre_usuario TEXT NOT NULL,
		hash           TEXT NOT NULL,
		nombre         TEXT
);

CREATE TABLE instalacion_usuario (
		usuario_id     INTEGER NOT NULL,
		instalacion_id INTEGER NOT NULL,
		FOREIGN KEY (usuario_id) REFERENCES usuario (id) ON DELETE CASCADE ON UPDATE CASCADE,
		FOREIGN KEY (instalacion_id) REFERENCES instalacion (id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- "Tipos de permiso" que se pueden usar.
-- La columna "tabla_relacionada" es opcional. Es el nombre de otra tabla, tal como "dashboard"
-- o "dispositivo", que contiene las filas concretas a las que se refiere el permiso. La columna
-- "id_relacionado" de "permiso_usuario" contendrá el ID de la fila concreta de esa tabla para la
-- que damos permiso al usuario.
-- Por ejemplo, para dar permiso a los usuarios para ver dashboards, el permiso puede ser:
--   (id=P, nombre='ver dashboard', tabla_relacionada='dashboard')
-- Y luego se dará permiso a un usuario con id=U para un dashboard con id=D en la tabla "permiso_usuario":
--   (usuario_id=U, permiso_id=P, id_relacionado=D)
CREATE TABLE permiso (
    id                SERIAL NOT NULL PRIMARY KEY,
		nombre            TEXT NOT NULL,
		tabla_relacionada TEXT
);
INSERT INTO permiso (id, nombre, tabla_relacionada) VALUES (1, 'iniciar sesion', NULL);
INSERT INTO permiso (id, nombre, tabla_relacionada) VALUES (2, 'ver dashboard', 'dashboard');

CREATE TABLE permiso_usuario (
    usuario_id     INTEGER NOT NULL,
		permiso_id     INTEGER NOT NULL,
		id_relacionado INTEGER,
		FOREIGN KEY (usuario_id) REFERENCES usuario (id) ON DELETE CASCADE ON UPDATE CASCADE,
		FOREIGN KEY (permiso_id) REFERENCES permiso (id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Un dashboard debe pertenecer a una instalación.
-- "opciones" puede contener un dict de pares "parámetro":valor para almacenar opciones de
-- configuración del dashboard.
CREATE TABLE dashboard (
    id             SERIAL NOT NULL PRIMARY KEY,
		instalacion_id INTEGER NOT NULL,
		nombre         TEXT NOT NULL,
		descripcion    TEXT,
		opciones       TEXT,
		FOREIGN KEY (instalacion_id) REFERENCES instalacion (id) ON DELETE CASCADE ON UPDATE CASCADE
);
