import ipaddress
import json
import sys
import time
from wsgiref.validate import validator
import requests
from configobj import ConfigObj
import cliente_plc
import logging
import paho.mqtt.client as mqtt
import msgpack

logging.basicConfig(filename='dispositivo-2.log', level=logging.DEBUG)

def _inicializarDatos():
    '''
    Método donde se inicializan todas las variables necesarias para el programa.
    Variables para conectar con el autómata:
        ip (string)
        puerto (int)
        rack (int)
        slot (int)
        variables (dict) => nombre_variable : dirección_de_la_variable
    Variables para conectar con Ubidots:
        token (string)
        dispositivo (string)
    @return dict{ip, puerto, rack, slot, variables} & dict{token, dispositivo}
    '''
    try:
        config = ConfigObj('config.ini')
        parametros_automata = config['CONFIGURACION_AUTOMATA']
        for clave in parametros_automata:
            if (clave not in('ip_automata','puerto_automata','rack_automata','slot_automata', 'VARIABLES_LECTURA')):
                raise Exception('[ERROR]: Error al indicar los parametros del autamata: \n\t{}'. format(parametros_automata))
        return parametros_automata
    except KeyError as e:
        logging.error('[ERROR]: Error al leer las claves del archivo de configuracion.\nClaves Incorrectas.')
        raise e
    except Exception as e:
        logging.error('[ERROR] Error al leer el archivo de configuración.')
        raise e

def _conectarAutomata(param_automata) -> cliente_plc.ClientePLCSiemens:
    '''
    Método que inicializa el cliente PLC y establece conexión.
    @param param_automata (dict): diccionario con los datos del autómata necesarios para
        conectar con él.
    @return cliente conectado con el PLC.
    '''
    try:
        try:
            ipaddress.ip_address(param_automata['ip_automata'])
        except:
            raise Exception('[ERROR]: Ip no valida: {}'.format(param_automata['ip_automata']))
        if (int(param_automata['rack_automata']) < 0):
            raise Exception('[ERROR]: Rack no valido: {}'.format(param_automata['rack_automata']))
        if (int(param_automata['slot_automata']) < 0 or int(param_automata['slot_automata']) > 10):
            raise Exception('[ERROR]: Slot no valido: {}'.format(param_automata['slot_automata']))
        if (int(param_automata['puerto_automata']) < 0 or int(param_automata['puerto_automata']) > 65535):
            raise Exception('[ERROR]: Puerto no valido: {}'.format(param_automata['puerto_automata']))
        clienteSiemens = cliente_plc.ClientePLCSiemens(ip=param_automata['ip_automata'], puerto=int(param_automata['puerto_automata']),
            rack=int(param_automata['rack_automata']), slot=int(param_automata['slot_automata']))
        # clienteSiemens.conectar()  # Conectará al entrar al bucle
        return clienteSiemens
    except ValueError as e:
        logging.error('[ERROR]: Error en la indicacion de los campos de conexion con el autómata.\n\t \
        ip:{} | puerto:{} | rack:{} | slot:{}'.format(param_automata['ip_automata'], param_automata['puerto_automata'],
            param_automata['rack_automata'], param_automata['slot_automata']))
        raise e
    except Exception as e:
        logging.error('[ERROR]: Error al conectar con el automata.')
        raise e

def enviarDatosUbidots(payload, token, dispositivo):
    '''
    Método que envía una petición POST al servicio de Ubidots para actualizar los datos.
    @param payload (Dict[nombre_variable, valor_variable])
    @param token (str)
    @param dispositivo (str)
    '''
    url = "http://industrial.api.ubidots.com"
    url = "{}/api/v1.6/devices/{}".format(url, dispositivo)
    headers = {"X-Auth-Token": token, "Content-Type": "application/json"}
    estado = 400
    intentos = 0
    try:
        while estado >= 400 and intentos <= 5:
            request = requests.post(url=url, headers=headers, json=payload)
            estado = request.status_code
            intentos += 1
            time.sleep(1)

        if estado >= 400:
            raise Exception("[ERROR] No se ha podido enviar datos a Ubidots,por favor revisa sus credenciales y su conexión a internet"+
            "\n\turl:{}".format(url))
        logging.info("[INFO] Su dispositivo de Ubidots ha sido actualizado")
    except requests.exceptions.ConnectionError as e:
        logging.error('[ERROR] Error, la conexión fue denegada. Error de conexión.')
        raise e
    except requests.exceptions.Timeout as e:
        logging.error('[ERROR] Error de conexión debido al TimeOut')
        raise e
    except requests.exceptions.InvalidURL as e:
        logging.error('[ERROR] La URL proporcionada no es válida, por favor cámbiela.')
        raise e
    except requests.exceptions.HTTPError as e:
        logging.error('[ERROR] Error, respuesta HTTP no válida.')
        raise e

def on_connect(client, userdata, flags, rc):
    logging.debug("Connected with result code "+str(rc))

def iniciarClienteMQTT():
    client = mqtt.Client()
    client.username_pw_set('usuario', password='1234')  # Usuario definido en Mosquitto
    client.tls_set(ca_certs='C:\Program Files\mosquitto\certs\ca.crt', certfile='C:\Program Files\mosquitto\certs\client.crt', keyfile='C:\Program Files\mosquitto\certs\client.key')
    client.tls_insecure_set(True)
    client.on_connect = on_connect 
    client.connect('192.168.1.52', 8883, 60)
    return client

def enviarDatosMQTT(cliente, id_instalacion, id_dispositivo, payload):
    new_payload = {'id_instalacion':id_instalacion, 'id_dispositivo':id_dispositivo, 'datos':payload}
    json.dumps(new_payload)

    cliente.publish('VIDIC/', msgpack.packb(new_payload))

def escribirValor(valor, payload):
    if (valor == True):
        payload['nivel_sosa'] = 1
        payload['nivel_acido'] = 1
    else:
        payload['nivel_sosa'] = 0
        payload['nivel_acido'] = 0

def simularTotalizadores(contador, payload):
    payload['totalizador_volumen_dia'] = contador
    payload['totalizador_volumen_total'] +=contador

if __name__ == '__main__':
    try:

        logging.debug("Inicio de la aplicacion.")
        param_automata = _inicializarDatos()
        logging.info('Datos inicializados:\n\t{}'.format(param_automata))
        clientePLC = _conectarAutomata(param_automata)
        clientePLC.desconectar_si_error_comunicacion = True
        logging.info('Conexion con el automata creada-no establecida.')
        logging.debug(param_automata['VARIABLES_LECTURA'])
        clientePLC.mapear_variables(param_automata['VARIABLES_LECTURA'])
        clienteMQTT = iniciarClienteMQTT()
    
    except Exception as e :
        logging.error('[ERROR]: El programa no ha podido arrancar correctamente.\n{}'.format(e))
        logging.debug('Fin de la aplicacion.\n')
        sys.exit()

    try:
        contador = 10; valor = True
        while True:
            try:
                if(not clientePLC.conectado):
                    clientePLC.conectar()
                    logging.info('Conexion con el automata establecida.')
                payload = clientePLC.leer_mapa_variables() 
                # logging.debug('Lectura de las variables:\n\t{}'.format(payload))

                contador -= 1
                logging.debug('Contador: {}'.format(contador))
                escribirValor(valor, payload)
                if (contador == 0):
                    valor = not valor
                    contador = 10
                
                # Añadir totalizadores
                #simularTotalizadores(contador, payload)

                # id_dispositivo e id_instalción
                id_dispositivo = '4321'
                id_instalacion = '1111'

                logging.debug('Lectura de las variables:\n\t{}'.format(payload))
                enviarDatosMQTT(clienteMQTT, id_instalacion, id_dispositivo, payload)
                logging.info('Datos enviados al broker MQTT.')
                print('Datos enviados por MQTT')
                time.sleep(5)
            except Exception as e:
                logging.error('[ERROR]: {}'.format(e))
                time.sleep(2)
    
    except KeyboardInterrupt:
        clientePLC.desconectar()
        logging.error('La aplicación ha sido cancelada.\n')
        logging.info('Fin de la aplicacion.\n')
    except Exception:
        clientePLC.desconectar()
        logging.error('Ha ocurrido un error inesperado.\n')
        logging.info('Fin de la aplicacion.\n')