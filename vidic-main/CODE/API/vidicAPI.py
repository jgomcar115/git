# Para correr la API: uvicorn vidicAPI:app --host 0.0.0.0 --port 8000 --reload
from datetime import datetime, timedelta
from time import sleep
from typing import Union
import psycopg2
from configobj import ConfigObj
import logging

from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, status, Header
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm 
from fastapi.middleware.cors import CORSMiddleware


logging.basicConfig(filename="vidicAPI.log", level=logging.DEBUG)

# Lista de hosts que pueden acceder a la API
origins = [
    # "http://localhost:8080",
    # "http://localhost/*",
    # "http://192.168.1.39/*",
    # "http://192.168.1.47/*",
    '*'
]

# Para obtener la clave secreta ejecuta: openssl rand -hex 32
SECRET_KEY = "fbf575814bd08c5c9ab6c97dfc8e02c956bd573099042268d3a3c502b9ccf826"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 20

def _iniciar_conexion_db():
    '''
    Método de inicialización de los parámetros necesarios para conectarse e interactuar con la base de datos.
    '''
    try:
        logging.debug('{} => Inicializando datos de la conexion con la base de datos...'.format(datetime.utcnow()))
        config = ConfigObj('APIconfig.ini')
        parametros_conexion_bd = config['CONEXION_BASE_DATOS']
        for clave in parametros_conexion_bd:
            if(clave not in ('host', 'database', 'user', 'password')):
                raise Exception('[ERROR]: Error al indicar los parámetros de la conexión a la base de datos')
        logging.debug('{} => Intentando conectar con la base de datos...'.format(datetime.utcnow()))
        conexion_db = psycopg2.connect(host=parametros_conexion_bd['host'], database=parametros_conexion_bd['database'],
            user=parametros_conexion_bd['user'], password=parametros_conexion_bd['password'])
        
        cur = conexion_db.cursor()
        logging.info('{} => Conexion con la base de datos establecida correctamente.'.format(datetime.utcnow()))
        return conexion_db, cur

    except Exception as err:
        raise err

def conectarConBD():
    intentos = 0
    while intentos < 30:
        try:
            global conexion_db, cursor
            conexion_db, cursor = _iniciar_conexion_db()
            break

        except psycopg2.OperationalError as err:
            logging.error('{} => [ERROR] Ha ocurrido un error en la conexión con la base de datos: {}'.format(datetime.utcnow(), err))
            sleep(2)
            intentos += 1

        except Exception as err:
            logging.error('{} => [ERROR] Ha ocurrido un error desconocido en la conexión con la base de datos: {}'.format(datetime.utcnow(), err))
            sleep(2)
            intentos += 1
    if intentos == 10:
        logging.error('{} => [ERROR] Intentos de conectar con la base de datos agotados: {}'.format(datetime.utcnow(), err))
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Problema con la base de datos. Conexion no establecida.',
        )

conectarConBD()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()

# Hablilitar la política CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins = origins,
    allow_credentials = True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Excepción si ocurre un error desconocido:
error_desconocido = HTTPException(
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
    detail='Problema con la API',
)

#-----------------------------------------------------------------------------------------------------------------------------------

class Token(BaseModel):
    access_token : str
    token_type : str
    usuario : dict

class TokenData:
    nombre_usuario: Union[str, None] = None

    def __init__(self, nombre_usuario) :
        self.nombre_usuario = nombre_usuario

class Usuario:
    nombre_usuario: str
    nombre : str

    def __init__(self, nombre_usuario, nombre):
        self.nombre_usuario = nombre_usuario
        self.nombre = nombre

#-----------------------------------------------------------------------------------------------------------------------------------

def _alfanumérico(cadena_de_texto: str) -> bool:
    ''' 
    Devuelve:
        - True si la cadena es alfanumérica.
        - False si no lo es.
    Con esto evitamos posibles ataques de SQL-injection a nuestra base de datos.
    '''
    return cadena_de_texto.strip().isalnum()

def _verificarContrasenya(nombre_usuario: str, plain_password: str) -> bool:
    '''
    Devuelve:
        - True si la contraseña proporcionada por el usuario coincide con la contraseña de la base de datos.
        - False en caso contrario.
    '''
    try:
        cursor.execute("SELECT U.hash FROM usuario AS U WHERE U.nombre_usuario = '"+nombre_usuario+"'")
        contra_hashed = cursor.fetchall()[0][0] #primer elemento
        return pwd_context.verify(plain_password, contra_hashed)


    except psycopg2.OperationalError as err:
        logging.error('{} => [ERROR] Ha ocurrido un error en la conexión con la base de datos: {}'.format(datetime.utcnow(), err))
        conectarConBD()

    except Exception as err:
        logging.error('{} => [ERROR] Error al verificar la contraseña del usuario: {}'.format(datetime.utcnow(), err))
        raise error_desconocido

    # Borrar
# def _getContrasenya(nombre_usuario: str) -> :
#     '''
#     Por implementar: el lugar de devolver la contraseña con el getUsuario, que sea un método a parte,
#     ya que getUsuario se usa también en contextos donde la contraseña no es necesaria.
#     '''
#     pass

def _getUsuario(nombre_usuario:str) -> Usuario:
    '''
    Devuelve:
        - Un objeto Usuario con los datos del usuario si este existe.

    Falta por implementar: Mirar si tiene permisos de inicio de sesión

    '''
    if (not _alfanumérico(nombre_usuario)): raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail='Usuario no válido',)
    try:
        cursor.execute("SELECT U.nombre_usuario, U.nombre FROM usuario AS U WHERE EXISTS(SELECT * FROM usuario AS U2 WHERE U2.nombre_usuario = '"+nombre_usuario+"') AND EXISTS (SELECT * FROM permiso_usuario AS PU WHERE PU.usuario_id = U.id AND PU.habilitado=true AND PU.permiso_id = (SELECT id FROM permiso WHERE nombre='iniciar sesion'))")
        usuario = cursor.fetchall()
        try:
            usuario = Usuario(nombre_usuario=usuario[0][0], nombre=usuario[0][1])
            return usuario
        
        except IndexError:
            return None

        except psycopg2.OperationalError as err:
            logging.error('{} => [ERROR] Ha ocurrido un error en la conexión con la base de datos: {}'.format(datetime.utcnow(), err))
            conectarConBD()

    except Exception as err:
        logging.error('{} => [ERROR] Error al obtener el usuario de la base de datos: {}'.format(datetime.utcnow(), err))
        raise error_desconocido

def _autenticarUsuario(nombre_usuario:str, contrasenya:str) -> Usuario:
    '''
    Devuelve:
        - Un objeto Usuario si el usuario existe, y la contraseña es correcta.
        - "None" si no cumple lo anterior.

        Sería mejor si solo devuelve un "OK" ya que el usuario se puede recoger en el método de arriba.
    '''
    usuario = _getUsuario(nombre_usuario)
    if usuario is None:
        return False
    if not _verificarContrasenya(usuario.nombre_usuario, contrasenya):
        return False
    return usuario

def _crearTokenAcceso(data:dict, expires_delta: Union[timedelta, None]=None) -> str:
    '''
    Devuelve un token de sesión generado con la clave secreta indicada y el algoritmo indicado en las constantes de arriba.
    '''
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, ALGORITHM)
    return encoded_jwt

async def getUsuarioActual(token: str = Depends(oauth2_scheme)) -> Usuario:
    '''
    Devuelve:
        - El objeto Usuario asociado al token, si solo si el token es válido.
        - Si no, devuelve el error "credenciales_exception".
    '''
    credenciales_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail='No tienes credenciales válidas',
        headers={"WWW-Authenticate":"Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        nombre_usuario: str = payload.get("sub")
        if nombre_usuario is None:
            raise credenciales_exception
        token_data = TokenData(nombre_usuario)
    except JWTError:
        raise credenciales_exception
    usuario = _getUsuario(nombre_usuario=token_data.nombre_usuario)
    if usuario is None:
        raise credenciales_exception
    else: 
        usuario.contrasenya = ''      # se podría evitar si no recuperásemos la contraseña con este método.
        return usuario

# async def getUsuarioActualActivo(usuario_actual: Usuario = Depends(getUsuario)) -> Usuario:
#     '''
#     No se muy bien como funciona este método, a lo mejor es prescindible.
#     '''
#     if usuario_actual.inactivo:
#         raise HTTPException(status_code=400, datail='Inactive user')
#     return usuario_actual

def _contarDashboards(nombre_usuario: str) -> int:
    '''
    Devuelve el número de dashboards que tiene el usuario dado.
    '''
    try:
        cursor.execute("SELECT COUNT(*) FROM dashboard AS D WHERE D.instalacion_id IN (SELECT IU.instalacion_id FROM instalacion_usuario AS IU WHERE IU.usuario_id = (SELECT U.id FROM usuario AS U WHERE U.nombre_usuario = '"+nombre_usuario+"'))")
        contador = cursor.fetchall()[0][0] #primer elemento
        return contador

    except psycopg2.OperationalError as err:
        logging.error('{} => [ERROR] Ha ocurrido un error en la conexión con la base de datos: {}'.format(datetime.utcnow(), err))
        conectarConBD()

    except Exception as err:
        logging.error('{} => [ERROR] Error al contar en número de dashboards del usuario: {}'.format(datetime.utcnow(), err))
        raise error_desconocido

def _obtenerDashboardsUsuario(nombre_usuario: str) -> dict:
    '''
    Devuelve un diccionario con un array con todos los nombres de los dashboards que corresponden al usuario dado.
        -> {'dashboards' : [nombre_dashboard_1, nombre_dashboard_2, ...]
    '''
    try:
        cursor.execute("SELECT D.nombre FROM dashboard AS D WHERE D.instalacion_id IN (SELECT IU.instalacion_id FROM instalacion_usuario AS IU WHERE IU.usuario_id = (SELECT U.id FROM usuario AS U WHERE U.nombre_usuario = '"+nombre_usuario+"'))")
        dashboards = cursor.fetchall()
        nombre_dashboards = []
        for dashboard in dashboards:
            nombre_dashboards.append(dashboard[0])
        return {'dashboards': nombre_dashboards}
    
    except psycopg2.OperationalError as err:
        logging.error('{} => [ERROR] Ha ocurrido un error en la conexión con la base de datos: {}'.format(datetime.utcnow(), err))
        conectarConBD()
    
    except Exception as err:
        logging.error('{} => [ERROR] Ha ocurrido un error al recuperar los dashboards del usuario: {}'.format(datetime.utcnow(), err))
        raise error_desconocido

def _recuperar_datos_historicos(id_dispositivo:int, fecha_inicio: int, fecha_fin: int) -> dict:
    '''
    Devuelve un diccionario con:
        - el nombre de las variables.
        - el valor de las variables en orden correspondiente al nombre.
    '''
    try:
        cursor.execute("SELECT * FROM dispositivo_{id_dispositivo} WHERE variable_momento BETWEEN {fecha_inicio} AND {fecha_fin}".format(id_dispositivo=str(id_dispositivo), fecha_inicio=fecha_inicio, fecha_fin=fecha_fin))
        datos_recuperados = cursor.fetchall()
        colnames = [desc[0] for desc in cursor.description]
        return {'variables':colnames,'datos':datos_recuperados}

    except psycopg2.OperationalError as err:
        logging.error('{} => [ERROR] Ha ocurrido un error en la conexión con la base de datos: {}'.format(datetime.utcnow(), err))
        conectarConBD()
    
    except Exception as err:
        logging.error('{} => [ERROR] Ha ocurrido un error al recuperar los datos historicos del dispositivo {}: {}'.format(datetime.utcnow(), id_dispositivo, err))
        raise error_desconocido

def _getColor(nombre_usuario: str) -> str:
    '''Método que devuelve el color corporativo asociado al usuario.'''
    try:
        cursor.execute("SELECT color FROM usuario WHERE nombre_usuario = '"+nombre_usuario+"')")
        color = cursor.fetchall()[0][0]
        return (color if color else None)

    except psycopg2.OperationalError as err:
        logging.error('{} => [ERROR] Ha ocurrido un error en la conexión con la base de datos: {}'.format(datetime.utcnow(), err))
        conectarConBD()
    
    except Exception as err:
        logging.error('{} => [ERROR] Ha ocurrido un error al recuperar el color corporativo del usuario: {}.'.format(datetime.utcnow(), err))
        raise error_desconocido

#------------------------------------------------------------------------------------------------------------------------------------
#   Llamadas a la API.

@app.get("/usuario")
async def usuario(Authorization: str | None = Header(default=None)):
    token = Authorization.split()[1]
    return await getUsuarioActual(token)

@app.get("/contar-dashboards")
async def contarDashboards(nombre_usuario: str):
    return {'count': _contarDashboards(nombre_usuario)}

@app.get("/dashboards")
async def dashboards(nombre_usuario: str):
    return _obtenerDashboardsUsuario(nombre_usuario)

@app.get("/dispositivo")
async def dispositivo(id_dispositivo:int, fecha_inicio:int, fecha_fin:int):
    return _recuperar_datos_historicos(id_dispositivo, fecha_inicio, fecha_fin)

@app.post("/token", response_model=Token)
async def token(nombre_usuario:str, contrasenya:str):
    usuario = _autenticarUsuario(nombre_usuario, contrasenya)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Usuario o constraseña incorrectas',
            headers={'WWW-Authenticate':'Bearer'},
        )
    usuario.contrasenya = ''
    usuario_json = {
        'nombre_usuario': usuario.nombre_usuario,
        'nombre': usuario.nombre
    }
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = _crearTokenAcceso(data={'sub':usuario.nombre_usuario}, expires_delta=access_token_expires)
    return {'access_token':access_token, "token_type":"bearer", "usuario": usuario_json}

@app.get("/color")
async def getcolor(nombre_usuario:str):
    return _getColor(nombre_usuario)