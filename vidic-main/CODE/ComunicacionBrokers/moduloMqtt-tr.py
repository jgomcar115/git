import datetime as datetime
import json
import multiprocessing
from queue import Queue
from sqlite3 import Timestamp
import sys
from typing import Dict, Optional
import paho.mqtt.client as mqtt
from configobj import ConfigObj
import logging
import msgpack

import os
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner
import multiprocessing

import psycopg2

logging.basicConfig(filename="com_mosquitto.log", level=logging.DEBUG)
comunicacion_mosquitto_log = logging.getLogger('com_mosquitto.log')

def _inicializarDatos():
    try:
        config = ConfigObj('inMQTT.ini')
        parametros_conexion_mosquitto = config['CONEXION_BROKER_MOSQUITTO']
        parametros_conexion_crossbar = config['CONEXION_BROKER_CROSSBAR']
        for clave in parametros_conexion_mosquitto:
            if(clave not in ('broker_cn', 'puerto', 'usuario', 'contrasenya', 'ruta_ca', 'ruta_cert', 'ruta_key', 'tls_version')):
                raise Exception('[ERROR]: Error al indicar los parametros de conexion al broker MOSQUITTO.')
        for clave in parametros_conexion_crossbar:
            if(clave not in ('url', 'realm')):
                raise Exception('[ERROR]: Error al indicar los parametros de conexion al broker CROSSBAR.')
        
        return parametros_conexion_mosquitto, parametros_conexion_crossbar
    except KeyError as err:
        comunicacion_mosquitto_log.error('[ERROR]: Error al leer las claves del archivo de configuracion.\nClaves Incorrectas.')
        raise err
    except Exception as err:
        comunicacion_mosquitto_log.error('[ERROR]: Error al leer el archivo de configuracion')
        raise err


#############################################################################################################################################
##################################                    COMUNICACIÓN MOSQUITTO               ##################################################
#############################################################################################################################################

def _iniciarClienteSuscriptorMosquitto(parametros_conexion):
    try:
        client = mqtt.Client()
        client.username_pw_set(parametros_conexion['usuario'],password=parametros_conexion['contrasenya'])
        client.tls_set(parametros_conexion['ruta_ca'], parametros_conexion['ruta_cert'], parametros_conexion['ruta_key'], tls_version=int(parametros_conexion['tls_version']))
        client.tls_insecure_set(True)
        client.on_connect = on_connect
        client.on_message = on_message
        client.cola_mensajes = parametros_conexion['queue']
        client.connect(parametros_conexion['broker_cn'], int(parametros_conexion['puerto']), 60)
        print('mosquitto conectado')
        return client
    except Exception as err:
        comunicacion_mosquitto_log.error('[ERROR]: Error al iniciar la suscripcion con el broker')
        raise err

def on_connect(client, userdata, flags, rc):
    comunicacion_mosquitto_log.debug("Connected with result code "+str(rc))
    client.subscribe("VIDIC/#") #topic al que suscribirse

def on_message(client, userdata, msg):
    try:
        topic = msg.topic.split("/")    # [VIDIC, id_instalcion, id_dispositivo]
        id_instalacion = topic[1]
        id_dispositivo = topic[2]
        # print(msg.topic + " " + str(msg.payload))
        payload = msgpack.loads(msg.payload)
        # print(payload)
        new_payload = {'timestamp': datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000.0, 'datos':payload}
        # new_payload = {'timestamp': datetime.datetime.utcfromtimestamp(0).total_seconds() * 1000.0, 'datos':payload}
        topic = id_instalacion + '.' + id_dispositivo
        json_payload = [topic, json.dumps(new_payload)]
        comunicacion_mosquitto_log.debug(json_payload)

        comunicacion_mosquitto_log.debug('Encolando el payload.')
        client.cola_mensajes.put(json_payload)
        almacenarDatosHistoricos(new_payload)    

    except Exception as err:
        comunicacion_mosquitto_log.error('[ERROR]: Error al recibir el payload de Mosquitto.')
        raise err

def conectarConMosquitto(parametros_conexion_broker: Dict[str,str]):
    try:
        cliente_suscriptor = _iniciarClienteSuscriptorMosquitto(parametros_conexion_broker)
        cliente_suscriptor.loop_forever()
    except Exception as err:
        cliente_suscriptor.disconnect()
        raise err


#############################################################################################################################################
##################################                    COMUNICACIÓN CROSSBAR                ##################################################
#############################################################################################################################################

class _socketCrossbarPublicador(ApplicationSession):

    def __init__(self, config: Optional[str] = None, cola_compartida:Queue=None):
        super().__init__()
        self.cola_compartida = cola_compartida

    def onJoin(self, details):
        print("Sesion con el Crossbar abierta.")
        while True:
            payload_en_cola = cola_compartida.get()
            # print('Desencolando el siguiente payload:')
            # print('{}'.format(payload_en_cola))
            self.enviarPayload(topic = payload_en_cola[0], payload= payload_en_cola[1])
    
    def enviarPayload(self, topic, payload):
        self.publish(topic, payload)


def conectarConCrossbar(publicador_crossbar, queue):
    prueba = _socketCrossbarPublicador(cola_compartida=queue)
    publicador_crossbar.run(prueba)


#############################################################################################################################################
##################################                    COMUNICACIÓN BD                      ##################################################
#############################################################################################################################################

def _iniciar_conexion_db():
    try:
        config = ConfigObj('inMQTT.ini')
        parametros_conexion_bd = config['CONEXION_BASE_DATOS']
        for clave in parametros_conexion_bd:
            if(clave not in ('host', 'database', 'user', 'password')):
                raise Exception('[ERROR]: Error al indicar los parámetros de la conexión a la base de datos')
        
        conexion_db = psycopg2.connect(host=parametros_conexion_bd['host'], database=parametros_conexion_bd['database'],
            user=parametros_conexion_bd['user'], password=parametros_conexion_bd['password'])
        
        cur = conexion_db.cursor()
        return conexion_db, cur

    except Exception as err:
        raise err

conexion_db, cursor = _iniciar_conexion_db()

def _crear_tabla_sql(nombre_tabla, lista_variables_tabla, variable_ts, ts_registro=None):
    sql = 'CREATE TABLE IF NOT EXISTS {} ({}'.format(nombre_tabla, 'ts INTEGER,' if ts_registro else '')
    for id_variable in lista_variables_tabla:
        nombre_variable = 'variable_' + str(id_variable)
        # Asumimos que todas las variables serán de tipo REAL excepto la de timestamp
        sql += '{} {},'.format(nombre_variable, 'REAL')
    sql += '{} {},'.format(variable_ts, 'NUMERIC')
    sql = sql[:-1] + ');'
    cursor.execute(sql)
    conexion_db.commit()

    # Crear indice sobre el campo de timestamp, si se ha especificado
    sql = 'CREATE INDEX IF NOT EXISTS {tabla}_{campo}_idx ON {tabla}({campo} ASC)'.format(tabla=nombre_tabla, campo=variable_ts)
    cursor.execute(sql)
    conexion_db.commit()

def almacenarDatosHistoricos(payload):
    timestamp = int(payload['timestamp'])
    datos_generales = payload['datos']
    nombre_tabla = 'dispositivo_{id_dispositivo}'.format(id_dispositivo=datos_generales['id_dispositivo'])
    try:
        cursor.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_catalog='vidic' AND table_schema='public' AND table_name='{}');".format(nombre_tabla))
        existe = cursor.fetchall()[0][0]
        datos = datos_generales['datos']
        if (not existe):
            _crear_tabla_sql(nombre_tabla, datos, 'variable_momento')
        else:
            pass
            # La tabla ya existe y por lo tanto no hay que crearla.

        datos['momento'] = timestamp
        sql='insert into {tabla} ('.format(tabla=nombre_tabla)
        valores = '('
        for id_variable in datos:
            nombre_variable = 'variable_' + id_variable
            sql += nombre_variable + ','
            valores += str(datos[id_variable]) + ','
        sql = sql[:-1] + ')'
        valores = valores[:-1] + ')'
        sql += ' VALUES ' + valores
        cursor.execute(sql)
        conexion_db.commit()
        print('Datos almacenados en la base de datos')

    except Exception as err:
        conexion_db.rollback()
        raise err

#############################################################################################################################################
##################################                    CÓDIGO PRINCIPAL                     ##################################################
#############################################################################################################################################

if __name__ == '__main__':
    try:
        comunicacion_mosquitto_log.debug('Inicio del modulo de entrada')
        parametros_conexion_mosquitto, parametros_conexion_crossbar = _inicializarDatos()
        comunicacion_mosquitto_log.debug('Datos inicializados:\n\t{}'.format(parametros_conexion_mosquitto))

        cola_compartida = multiprocessing.Queue()

        parametros_conexion_mosquitto['queue'] = cola_compartida
    
        publicador_crossbar = ApplicationRunner(url= os.environ.get('CBURL', parametros_conexion_crossbar['url']), realm= os.environ.get('CBREALM', parametros_conexion_crossbar['realm']))

    except Exception as err:
        comunicacion_mosquitto_log.error('[ERROR]: El programa no ha podido arrancar correctamente.\n{}'.format(err))
        comunicacion_mosquitto_log.debug('Fin de la aplicacion.\n')
        sys.exit()
    
    try:
        multiprocessing.set_start_method('fork', force=True)
        procesos = [
            multiprocessing.Process(target=conectarConCrossbar, args=([publicador_crossbar, cola_compartida])),
            multiprocessing.Process(target=conectarConMosquitto, args=([parametros_conexion_mosquitto]))
        ]
        for proceso in procesos:
            proceso.start()
    
    except Exception as err:
        comunicacion_mosquitto_log.error('Ha ocurrido un error inesperado.\n{}'.format(err))
        comunicacion_mosquitto_log.info('Fin de la aplicacion.\n')
        conexion_db.close()
        raise err
