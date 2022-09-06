import sys
import paho.mqtt.client as mqtt
from configobj import ConfigObj
import logging
import msgpack


logging.basicConfig(filename="entrada_datos.log", level=logging.DEBUG)

def _inicializarDatos():
    try:
        config = ConfigObj('inMQTT.ini')
        parametros_conexion_broker = config['CONEXION_BROKER']
        for clave in parametros_conexion_broker:
            if(clave not in ('broker_cn', 'puerto', 'usuario', 'contrasenya', 'ruta_ca', 'ruta_cert', 'ruta_key', 'tls_version')):
                raise Exception('[ERROR]: Error al indicar los parametros de conexion al broker.')
        return parametros_conexion_broker
    except KeyError as err:
        logging.error('[ERROR]: Error al leer las claves del archivo de configuracion.\nClaves Incorrectas.')
        raise err
    except Exception as err:
        logging.error('[ERROR]: Error al leer el archivo de configuracion')
        raise err

def _iniciarClienteSuscriptor(parametros_conexion):
    try:
        client = mqtt.Client()
        client.username_pw_set(parametros_conexion['usuario'],password=parametros_conexion['contrasenya'])
        client.tls_set(parametros_conexion['ruta_ca'], parametros_conexion['ruta_cert'], parametros_conexion['ruta_key'], tls_version=int(parametros_conexion['tls_version']))
        client.tls_insecure_set(True)
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(parametros_conexion['broker_cn'], int(parametros_conexion['puerto']), 60)
        return client
    except Exception as err:
        logging.error('[ERROR]: Error al iniciar la suscripcion con el broker')
        raise err

def on_connect(client, userdata, flags, rc):
    logging.debug("Connected with result code "+str(rc))
    client.subscribe("VIDIC/#") #topic al que suscribirse

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    logging.debug(msg.topic + " " + str(msg.payload))
    print(msg.topic + " " + str(msg.payload))
    test = msgpack.loads(msg.payload)
    payload = msgpack.unpackb(msg.payload, raw=True)
    #print(payload)
    print(test)
    print(test['datos']['medida_ph'])

if __name__ == '__main__':
    try:
        logging.debug('Inicio del modulo de entrada')
        parametros_conexion_broker = _inicializarDatos()
        logging.debug('Datos inicializados:\n\t{}'.format(parametros_conexion_broker))
        cliente_suscriptor = _iniciarClienteSuscriptor(parametros_conexion_broker)
    except Exception as err:
        logging.error('[ERROR]: El programa no ha podido arrancar correctamente.\n{}'.format(err))
        logging.debug('Fin de la aplicacion.\n')
        sys.exit()
    
    try:
        logging.debug('El cliente se ha conectado correctamente, inicia el bucle.')
        cliente_suscriptor.loop_forever()
    
    except Exception:
        cliente_suscriptor.disconnect()
        logging.error('Ha ocurrido un error inesperado.\n')
        logging.info('Fin de la aplicacion.\n')