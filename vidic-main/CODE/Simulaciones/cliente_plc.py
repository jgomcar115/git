#!/usr/bin/env python3
# encoding: utf-8
''' Comunicación con PLCs por TCP

La comunicación con Siemens (Profinet) se hace a través de la librería snap7.
Es una librería C++, así que usamos ctypes para llamar a las funciones
de la DLL snap7.dll (que debe estar accesible en el path).

Para comunicación Modbus/TCP, no hay ninguna dependencia externa.

Requiere el paquete "pywin32".
'''
import logging

# Enumeraciones
from enum import IntEnum
from multiprocessing.dummy import Array
# Conversión de arrays de bytes a valores en tipos Python
import struct
# Comunicación TCP/IP
import socket
# Comprobación de IPs válidas
import ipaddress
# Pausa, tiempo ejecución
import time
# Expresiones regulares
import re
# Truncamiento a entero
import math
# Diccionarios que mantienen orden inserción
from collections import OrderedDict
# Generador de números aleatorios enteros
from random import randint
# Librerías de sistema
import os
import sys
import platform
import subprocess
# Validación de tipos
from typing import Any, Tuple, Dict, List, Union, NoReturn, Optional
# Llamadas a funciones externas en C
import ctypes
import ctypes.util
if platform.system().lower().startswith('win'):
    # En Windows, importar definición de HANDLE en wintypes
    import win32api
    import ctypes.wintypes
    CTYPES_HANDLE = ctypes.wintypes.HANDLE
    ctypes_cdll = ctypes.WinDLL
else:
    # En otros sistemas, copiamos aquí la definición de HANDLE
    # en wintypes: un puntero a void
    CTYPES_HANDLE = ctypes.c_void_p #type: ignore
    ctypes_cdll = ctypes.CDLL  #type: ignore


# Para hacer los métodos "thread safe", usamos objetos mutex.
# Esto impide que se puedan hacer accesos simultáneos al PLC
# aunque se hagan llamadas desde múltiples hilos de ejecución.
# Si THREADSAFE está a False, no se usan mutex; si se pone a True,
# se usan objetos Lock de la librería estándar de Python.
THREADSAFE = True
if THREADSAFE:
    from threading import Lock

# Usamos el log del módulo principal. Para aplicaciones estándar es suficiente;
# para aplicaciones tales como servicios, __name__ no es el nombre del módulo
# principal, sino "cliente_plc". Para estos casos,asignar desde el módulo principal
# un nuevo logger a la variable "log" de este módulo.
log = logging.getLogger(__name__)
# Creamos un nivel de log específico para el módulo, por debajo del nivel DEBUG normal;
# así el módulo no emitirá mensajes de depuración si no se "fuerza" un nivel de log.
# Usamos logging.DEBUG - 3 para dejar margen a niveles de depuración por debajo
DEBUG_CLIENTE_PLC = logging.DEBUG - 3

# Usamos la librería asyncua para poder comunicarnos con dispositivos a través del
# protocolo OPC-UA. En este caso usamos un módulo síncrono para realizar las 
# comunicaciones.
from asyncua.sync import Client
from asyncua import ua


def asignar_logger(logger):
    ''' Asigna a este módulo un objeto "log" externo
    '''
    global log
    log = logger

#############################################################################
# Funciones auxiliares
# Las incluimos en el código para que no haya dependencias externas
#############################################################################

def ping2(ip, intentos=2, timeout=100):
    ''' Devuelve True si la IP indicada responde al comando "ping".
    La diferencia con el ping estándar es que cada intento se hace con una
    llamada separada al comando "ping" del sistema, y en el primer intento
    en que haya respuesta, finaliza y devuelve True.
    @param ip Dirección IP (en forma de cadena "nnn.nnn.nnn.nnn")
    @param intentos a realizar; por defecto, 2
    @param timeout en milisegundos del comando; por defecto, 100 (=1 décima de segundo)
    '''
    for _ in range(intentos):
        if platform.system().lower().startswith('win'):
            comando = ['ping', '-n', '1', '-w', str(timeout), ip]
            resultado = subprocess.run(
                comando, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,
                check=False
            )
            if resultado.returncode == 0 and b'TTL=' in resultado.stdout:
                return True
        else:
            comando = ['ping', '-c', '1', '-w', str(timeout), ip]
            resultado = subprocess.run(
                comando,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
            if resultado.returncode == 0:
                return True
    # Hemos agotado los intentos sin obtener respuesta
    return False


#############################################################################
# Excepciones que pueden generar las funciones de comunicación
#############################################################################

class PLCError(Exception):
    ''' Error en una función del módulo cliente_plc.
    Esta clase se usa como base para el resto de excepciones, que son más
    específicas (y que habría que comprobar antes). Si se genera una excepción
    de este tipo, suele deberse a errores en los parámetros pasados a las
    funciones.
    '''
    def __init__(self, mensaje_error: Optional[str]=None):
        ''' Constructor: almacena el mensaje que describe el error
        '''
        super().__init__(mensaje_error)
        self.mensaje = mensaje_error

    def mensaje_error(self):
        ''' getter
        '''
        return self.mensaje


class PLCErrorLibreria(PLCError):
    ''' Error al inicializar la librería DLL de comunicación.
    '''
    def __init__(self, mensaje_error: Optional[str]=None):
        ''' Constructor. Si no recibe un mensaje de error concreto,
        usa un mensaje genérico de error en librería.
        '''
        if mensaje_error is None:
            mensaje_error = 'Error al cargar la librería DLL de comunicación'
        super().__init__(mensaje_error)


class PLCErrorComunicacion(PLCError):
    ''' Error en la comunicación con el PLC.
    '''
    def __init__(self, mensaje_error:Optional[str]=None):
        ''' Constructor. Si no recibe un mensaje de error concreto,
        usa un mensaje genérico de error de comunicación.
        '''
        if mensaje_error is None:
            mensaje_error = 'Error en la comunicación con el dispositivo'
        super().__init__(mensaje_error)


class PLCErrorModbus(PLCError):
    ''' Error en una llamada Modbus.
    '''
    __mapa_codigos_mensajes_error_modbus = {
        0: 'No hay error',
        1: 'Código de función no válido',
        2: 'Dirección de datos no válida',
        3: 'Valor del campo de petición no válido',
        4: 'Ha ocurrido un error no recuperable',
        5: 'Procesando petición de larga duración',
        6: 'Dispositivo ocupado',
        7: 'No se puede realizar la función de programación',
        8: 'Error de paridad en la memoria extendida',
        11: 'Error en la puerta de enlace',
        12: 'No hay respuesta de la puerta de enlace'
    }

    def __init__(self, codigo_error: int, mensaje_error: Optional[str]=None):
        ''' Constructor. Si no recibe un mensaje de error concreto,
        usa un mensaje de error a aprtir del código de error modbus recibido.
        '''
        self.codigo = codigo_error
        if (mensaje_error is None) and (
                self.codigo in PLCErrorModbus.__mapa_codigos_mensajes_error_modbus.keys()
        ):
            mensaje_error = PLCErrorModbus.__mapa_codigos_mensajes_error_modbus[self.codigo]
        super().__init__(mensaje_error)

    def codigo_error(self):
        ''' getter
        '''
        return self.codigo


class PLCErrorSiemens(PLCError):
    ''' Error en una llamada a una función snap7.
    Esta excepción se genera cuando es el dispositivo (PLC)
    el que devuelve un error. Si el error es por la comunicación,
    se generará una excepción PLCErrorComunicacion.
    '''

    def __init__(self, codigo_error: int, mensaje_error: Optional[str]=None):
        ''' Constructor
        '''
        self.codigo = codigo_error
        super().__init__(mensaje_error)

    def codigo_error(self):
        ''' getter
        '''
        return self.codigo

class PLCErrorOpcUa(PLCError):
    ''' Error en una llamada a una función de asyncua.
    Esta excepción se genera cuando ha habido un error en la conexión
    OPC-UA.
    '''
    def __init__(self, codigo_error: Optional[int]=None, mensaje_error: Optional[str]=None):
        '''Constructor'''
        if(codigo_error is None):
            mensaje_error = 'Error interno de la librería: ', mensaje_error    
        self.codigo = codigo_error
        super().__init__(mensaje_error)

    def codigo_error(self):
        ''' getter
        '''
        return self.codigo


#############################################################################
# Clases de comunicación: clase base y clases derivadas para distintos tipos
# de comunicación
#############################################################################


# Tipos de datos que se pueden leer o escribir
class TipoDatos(IntEnum):
    ''' Tipos de datos que se pueden leer o escribir
    '''
    entero = 1
    entero_largo = 2
    entero_sin_signo = 3
    entero_sin_signo_largo = 4
    real = 5
    real_doble = 6
    booleano = 7
    byte = 8
    entero_largo_doble = 9
    entero_sin_signo_largo_doble = 10

CARACTER_TIPO_DATOS = {
    ''' Caracteres indicadores de formato, para especificaciones del tipo de
    variables en los mapas nombre variable -> formato+posición.
    Una variable se puede definir usando el tipo seguido de su dirección:
    por ejemplo, w2 = word en posición (o registro Modbus) 2; b5 = byte en
    posición 5.
    Los valores bool pueden definirse con carácter x o sin carácter, ya que se
    reconocen porque la dirección tiene la forma dirección.bit; por ejemplo, bit
    0 de posición 8: x8.0 o 8.0. Importante: si pueden usarse índices de bit
    mayores que 9 (para direccionar un bit en un word o doble word), los índices
    de bit 1..9 deben ir precedidos de un 0 (0.01, 0.02..0.09, 0.10, 0.11..)
    Las direcciones Siemens llevarán además un prefijo con el área de la que se
    leen, compuesto por tipo de area y número; por ejemplo, db2.w0 = área DB 2,
    word posición 0.
    '''
    '': TipoDatos.booleano,
    'x': TipoDatos.booleano,
    'b': TipoDatos.byte,
    'w': TipoDatos.entero_sin_signo,
    'dw': TipoDatos.entero_sin_signo_largo,
    'i': TipoDatos.entero,
    'di': TipoDatos.entero_largo,
    'r': TipoDatos.real,
    'dr': TipoDatos.real_doble,
    'qi': TipoDatos.entero_largo_doble,
    'qw': TipoDatos.entero_sin_signo_largo_doble
}



class ClientePLC:
    ''' Objeto cliente para comunicación con PLCs o dispositivos Modbus.
    '''
    # Cadena de formato necesaria para extraer el valor del byte array devuelto
    _cadena_formato_tipo_datos = {
        TipoDatos.entero:'h',
        TipoDatos.entero_largo:'i',
        TipoDatos.entero_sin_signo:'H',
        TipoDatos.entero_sin_signo_largo:'I',
        TipoDatos.real:'f',
        TipoDatos.real_doble:'d',
        TipoDatos.booleano:'B',
        TipoDatos.byte:'c',
        TipoDatos.entero_largo_doble:'q',
        TipoDatos.entero_sin_signo_largo_doble:'Q',
    }
    # Tamaño (en bytes) de cada tipo de datos
    # Las clases derivadas pueden redefinir estos tamaños
    _bytes_tipo_datos = {
        TipoDatos.entero:2,
        TipoDatos.entero_largo:4,
        TipoDatos.entero_sin_signo:2,
        TipoDatos.entero_sin_signo_largo:4,
        TipoDatos.real:4,
        TipoDatos.real_doble:8,
        TipoDatos.booleano:1,
        TipoDatos.byte:1,
        TipoDatos.entero_largo_doble:8,
        TipoDatos.entero_sin_signo_largo_doble:8,
    }
    # Expresión regular con el formato de las direcciones de variables, separando las partes
    # de la dirección: area, tipo, dirección y bit (todos opcionales excepto dirección).
    # Caso especial para Modbus: si no se usa nombre del área y se especifica una variable booleana
    # (en formato xN.M), se interpretaría que xN es el área. Así que excluimos la x del primer elemento
    # de la expresión regular.
    er_direccion = re.compile(r'^([a-wyz]+[0-9]*\.)?([a-z]+)?([0-9]+)(\.[0-9]+)?$')

    def __init__(self, ip: Optional[str]=None, puerto: Optional[int]=None):
        ''' Constructor.
        @param ip (str): Dirección IPv4 del dispositivo, en forma de cadena
            ("a.b.c.d").
        @param puerto (int, opcional): Puerto TCP a usar para la comunicación.
            Si no se indica, se usará el número de puerto por defecto para
            cada tipo de dispositivo.
        '''
        self.ip = ip
        self.puerto = puerto
        # Número de bytes que se recuperan en cada lectura.
        # Por defecto asumimos que se leen registros de 1 byte.
        # Las clases derivadas pueden cambiar este valor si los registros que
        # devuelve el dispositivo tienen 2 o más bytes.
        self.bytes_por_registro = 1
        # Máximo número de registros que se pueden leer en una sola operación.
        # Modbus está limitado a 123 registros por lectura. Siemens, aunque tiene
        # un límite de tamaño de PDU entre 240 a 960 bytes, al acceder con la
        # librería Snap7 no importa; la propia librería divide la llamada en
        # fragmentos más pequeños.
        self.max_registros_por_lectura = 65535
        # Order de los bytes (endianess) que usa el dispositivo.
        # Se usan los caracteres de las cadenas de formato de la función
        # unpack(). Por defecto usamos '@', que significa usar el formato
        # nativo del sistema.
        # Las clases derivadas pueden cambiarlo por '<' para little-endian
        # (byte menos significativo primero), '>' para big-endian (byte más
        # significativo primero).
        # Los PLC Siemens internamente son BIG endian, almacenando los bytes
        # del más al menos significativo:
        # ejemplo, el DWORD 0x4C21112F se almacena en 4 bytes 0x4C 0x21 0x11 0x2F
        # Modbus también usa por defecto big-endian para los registros.
        # En cambio, los PC Intel/AMD son LITTLE Endian: 0x2F 0x11 0x21 0x4C
        self.orden_bytes = '@'
        # Algunos dispositivos (Modbus) almacenan valores de más de 16 bits
        # en orden inverso a su "endianess", por lo que hay que invertir las
        # "palabras" (16 bits) al leer o escribir valores.
        self.invertir_palabras = False
        # Algunos dispositivos (Modbus) además invierten los bytes dentro de
        # cada palabra.
        self.invertir_bytes = False
        # Ajuste: si True, cuando se produce cualquier error de comunicación
        # TCP, el objeto PLC se desconecta automáticamente.
        # Ojo: si este parámetro se deja a False, el objeto cliente puede
        # tener la propiedad conectado a True, pero no responder a la
        # comunicación.
        self.desconectar_si_error_comunicacion = False
        # Ajuste: si True, no es necesario llamar al método conectar() antes
        # de acceder al PLC; se llama automáticamente. Ojo: si se pone este
        # ajuste a True, hay que pasar en el constructor los parámetros de la
        # conexión (ip, rack/slot o número dispositivo)
        self.conectar_automaticamente = False

        # Indicador de si está abierta la conexión con el dispositivo.
        # Las clases derivadas, en los métodos conectar/desconectar,
        # deben actualizar este valor.
        self._conectado = False
        # Mapa de direcciones variables: diccionario
        #   {'nombre_area': diccionario {dirección: tipo}}
        # con las áreas de las que leer, y en cada una un mapa de las
        # direcciones a que acceder y el tipo que se almacena en esa
        # dirección.
        # Según el tipo de dispositivo, el nombre de área puede ser:
        #    Siemens:
        #       'dbN' = DB número N;
        #       'mk' = marcas
        #    Modbus:
        #       'co' = coils (salidas digitales)
        #       'in' = inputs (entradas digitales)
        #       'ir' = input registers (entradas analógicas)
        #       'hr' = holding registers (salidas analógicas)
        # Creamos el mapa por defecto con la clave None, de forma que si no se
        # pasa un nombre de mapa, la función recibirá el valor por defecto None
        # y se puede usar directamente como clave del mapa a usar.
        self._mapa_direcciones = {None: OrderedDict()}
        # Mapa de variables: diccionario {
        #   nombre_mapa:diccionario {
        #       'nombre_area': diccionario {direccion: nombre_variable}
        #   }
        # }
        # con las áreas de las que se lee en cada mapa, y para cada una un diccionario
        # con un mapa de las direcciones que se acceden y el nombre de variable
        # que se ha dado a esa dirección.
        self._mapa_variables = {None: OrderedDict()}
        # Rangos de posiciones que hay que leer en cada área de cada mapa: diccionario{
        #   nombre_mapa:diccionario{
        #       'nombre_area': [(direccion_min, direccion_max, num_registros)]
        #   }
        # }
        # (siempre será una lista de tuplas, cada una corresponde a una lectura)
        self._rango_direcciones = {None: OrderedDict()}
        self._DIRECCION_MIN = 0
        self._DIRECCION_MAX = 1
        self._NUM_REGISTROS = 2
        # Mutex para evitar ejecución simultánea de dos accesos al dispositivo
        if THREADSAFE:
            self.mutex_acceso = Lock()
        # Pausa en segundos tras cada lectura o escritura, para evitar "colapsar" al PLC
        # Se usa solo en modo "THREADSAFE"
        self.pausa_entre_accesos = 0.1 # 60 milisegundos
        # Timeout en segundos para adquirir un bloqueo de acceso
        ### (de momento solo en lecturas Siemens)
        self.timeout_acceso = 1

    def conectar(self, *args, **kwargs):
        ''' Abre la conexión con el PLC.
        Si ya está abierta una conexión al mismo PLC, no se hace nada;
        por lo que se puede llamar a esta función repetidamente.
        Cada clase derivada añadirá en la redefinición de este método
        los parámetros que necesite la conexión a esa clase de dispositivo.
        '''
        raise NotImplementedError()

    def desconectar(self):
        ''' Cierra la conexión con el PLC.
        '''
        raise NotImplementedError()

    @property
    def conectado(self):
        ''' Devuelve True si está abierta la conexión al PLC.
        '''
        return self._conectado


    def _bytes_a_valor(self, array_bytes: bytes, tipo: TipoDatos, indice_bit: int=0) -> Any:
        ''' Convierte un valor en bruto (array de bytes) a un valor Python.
        Si hay un error en la conversión, devuelve None.
        @param array_bytes: Byte array con el valor tal como ha sido devuelto
            por el PLC
        @param tipo: TipoDatos al que convertir el valor
        @param indice_bit: Para tipo booleano, el índice del bit a leer.
            Si no se indica, se usa el bit 0.
        '''
        # La respuesta es de tipo bytes, con el valor codificado según el tipo
        # mapeado en el PLC. Preparamos una cadena de formato para extraer el
        # valor en el tipo adecuado, teniendo en cuenta el orden de los bytes
        # (endianess) de los valores que devuelve el PLC.
        try:
            cadena_formato = self.orden_bytes + self._cadena_formato_tipo_datos[tipo]
            # Si el PLC almacena valores de más de 16 bits con las palabras en orden inverso
            # a su "endianess", intercambiar el orden de las "palabras" (palabra = 16 bits).
            # Esto suele ser necesario solo para dispositivos Modbus.
            if len(array_bytes) == 4 and self.invertir_palabras:
                array_bytes = bytes((
                    array_bytes[2], array_bytes[3], array_bytes[0], array_bytes[1]
                ))
            elif len(array_bytes) == 8 and self.invertir_palabras:
                array_bytes = bytes((
                    array_bytes[6], array_bytes[7], array_bytes[4], array_bytes[5],
                    array_bytes[2], array_bytes[3], array_bytes[0], array_bytes[1]
                ))
            # Si además hay que invertir los bytes dentro de cada palabra:
            if len(array_bytes) == 4 and self.invertir_bytes:
                array_bytes = bytes((
                    array_bytes[1], array_bytes[0], array_bytes[3], array_bytes[2]
                ))
            elif len(array_bytes) == 8 and self.invertir_bytes:
                array_bytes = bytes((
                    array_bytes[1], array_bytes[0], array_bytes[3], array_bytes[2],
                    array_bytes[5], array_bytes[4], array_bytes[7], array_bytes[6]
                ))
            # La función unpack siempre devuelve una tupla, aunque se extraiga
            # un solo valor.
            valor = struct.unpack(cadena_formato, array_bytes)[0]
            # Caso especial: los valores booleanos son 1 bit dentro del byte
            # leido; hacemos una operación and para aislar el bit que hay que
            # devolver, y devolvemos true si el bit es 1 o false si es 0
            if tipo == TipoDatos.booleano:
                valor = (valor & (1 << indice_bit) != 0)
            return valor
        except Exception as e:
            log.log(DEBUG_CLIENTE_PLC,
                'ERROR _bytes_a_valor(array_bytes=%s, tipo=%s, indice_bit=%s): %s',
                array_bytes, tipo, indice_bit, e
            )
            return None

    def _valor_a_bytes(self, valor: Any, tipo: TipoDatos, indice_bit: int=0) -> bytes:
        ''' Convierte un valor Python a un valor en bruto (array de bytes).
        @param valor: Valor a convertir
        @param tipo: TipoDatos al que convertir el valor.
            Nota: Si tipo es booleano, se devuelve un byte con el bit indice_bit
            a 0 o 1, dependiendo de si valor es True o False, y el resto de bits
            todos a 0.
        @param indice_bit: (Opcional) Para tipo booleano, el índice del bit a leer.
            Si no se indica, se usa el bit 0.
        @return: Byte array con valor codificado
        '''
        # Caso especial: los valores booleanos son 1 bit dentro del byte leido; si el valor es True,
        # se pone a 1 el bit que corresponde (desplazando el bit hasta la posición indicada)
        if tipo == TipoDatos.booleano:
            valor = (1 << indice_bit) if valor else 0
        # La respuesta es de tipo bytes, con el valor codificado según el tipo mapeado en el PLC.
        # Preparamos una cadena de formato para convertir el valor, teniendo en
        # cuenta el orden de los bytes (endianess) de los valores que devuelve el PLC.
        cadena_formato = self.orden_bytes + self._cadena_formato_tipo_datos[tipo]
        # Caso especial: si se recibe un valor byte para TipoDatos.byte, pero la cadena de
        # formato no usa el tipo "c", convertir valor a entero
        if tipo == TipoDatos.byte and isinstance(valor, bytes) and self._cadena_formato_tipo_datos[tipo] != 'c':
            valor = int.from_bytes(valor, 'little' if self.orden_bytes == '<' else 'big')
        array_bytes = struct.pack(cadena_formato, valor)
        # Si el PLC almacena valores de más de 16 bits con las palabras en orden inverso
        # a su "endianess", intercambiar el orden de las "palabras" (palabra = 16 bits).
        # Esto suele ser necesario solo para dispositivos Modbus.
        if len(array_bytes) == 4 and self.invertir_palabras:
            array_bytes = bytes((
                array_bytes[2], array_bytes[3], array_bytes[0], array_bytes[1]
            ))
        elif len(array_bytes) == 8 and self.invertir_palabras:
            array_bytes = bytes((
                array_bytes[6], array_bytes[7], array_bytes[4], array_bytes[5],
                array_bytes[2], array_bytes[3], array_bytes[0], array_bytes[1]
            ))
        # Si además hay que invertir los bytes dentro de cada palabra:
        if len(array_bytes) == 4 and self.invertir_bytes:
            array_bytes = bytes((
                array_bytes[1], array_bytes[0], array_bytes[3], array_bytes[2]
            ))
        elif len(array_bytes) == 8 and self.invertir_bytes:
            array_bytes = bytes((
                array_bytes[1], array_bytes[0], array_bytes[3], array_bytes[2],
                array_bytes[5], array_bytes[4], array_bytes[7], array_bytes[6]
            ))
        return array_bytes


    def _separar_direccion_bit(self, direccion: float) -> Tuple[int, int]:
        ''' Devuelve una dirección de bit, en forma de número real xxx.yy
        (xxx = dirección registro, yy = índice del bit en el registro)
        separada en parte entera xxx y parte decimal yy.
        Si direccion no tiene parte decimal, se devuelve None como parte decimal.
        '''
        # Se podría usar math.modf, pero devuelve dos números reales y puede dar
        # problemas la parte decimal por precisión; convertimos la dirección a una
        # cadena, la dividimos por el punto decimal y convertimos la parte entera en
        # el número de registro y la parte decimal en el índice del bit.
        direccion_registro = 0
        indice_bit = 0
        try:
            direccion_str = str(direccion).split('.')
            if len(direccion_str) > 1:
                indice_bit = int(direccion_str[1])
            direccion_registro = int(direccion_str[0])
        except Exception:
            pass
        return (direccion_registro, indice_bit)


    def _rango_posiciones(self, lista_posiciones: Dict[Union[int, float], TipoDatos]) -> List[Tuple[int, int, int]]:
        ''' Devuelve una lista de tuplas (direccion_minima, direccion_maxima, numero_registros)
        que se necesitan para leer el mapa de variables que se pasa como parámetro.
        Si se devuelve más de una tupla, es porque hay que leer los valores en más de una
        llamada, por la limitación del dispositivo.
        @param lista_posiciones: dict {posicion:tipo} de las variables.
        '''
        def num_registros_posicion(posicion):
            return self._bytes_tipo_datos[lista_posiciones[posicion]] // self.bytes_por_registro

        def _min_max_num(minimo, maximo):
            # Por si las direcciones son de bit, truncamos:
            direccion_min = math.trunc(minimo)
            direccion_max = math.trunc(maximo)
            # Hay que contar con el número de registros que conforman el último valor
            return(direccion_min, direccion_max, direccion_max - direccion_min + num_registros_posicion(maximo))

        # Para leer en una sola llamada todos los valores, calculamos el número de registros
        # que hay entre la direcciones más baja a leer y la más alta
        direcciones = sorted(lista_posiciones.keys())
        direccion_min = direcciones[0]
        direccion_max = direcciones[-1]
        (registro_min, registro_max, num_registros) = _min_max_num(direccion_min, direccion_max)
        log.log(DEBUG_CLIENTE_PLC, '   _rango_posiciones: (%s,%s,%s)', registro_min, registro_max, num_registros)
        if num_registros > self.max_registros_por_lectura:
            indice_corte = ultimo_corte = 0
            resultado = []
            while indice_corte < len(direcciones):
                # Contar con el número de registros que conforman la posición de corte.
                if math.trunc(direcciones[indice_corte]) + num_registros_posicion(direcciones[indice_corte]) \
                        > math.trunc(direcciones[ultimo_corte]) + self.max_registros_por_lectura:
                    resultado.append(_min_max_num(direcciones[ultimo_corte], direcciones[indice_corte - 1]))
                    ultimo_corte = indice_corte
                indice_corte += 1
            if indice_corte > ultimo_corte:
                resultado.append(_min_max_num(direcciones[ultimo_corte], direcciones[indice_corte - 1]))
            log.log(DEBUG_CLIENTE_PLC, resultado)
            return resultado
        else:
            return [(registro_min, registro_max, num_registros)]

    @staticmethod
    def separar_direccion(direccion):
        ''' Separa "direccion" en una tupla (area, tipo, posicion) y la devuelve.
        Si la variable es booleana, "direccion" será un número real con parte entera=dirección
        y parte decimal=número bit.
        Para el formato de "direccion", ver el método "mapa_variables".
        Se genera una excepción PLCError si hay un error en la dirección.
        '''
        # Dividir la dirección en 4 fragmentos: "area.", "tipo", "posición" y ".bit"
        partes_direccion = re.findall(ClientePLC.er_direccion, direccion.lower().strip())
        # re.findall devuelve una lista de tuplas; si la lista está vacía, la dirección
        # no tiene el formato correcto. Si no, quedarnos con la primera tupla de la lista,
        # cuyos elementos son el contenido de cada paréntesis de la expresión regular
        if not partes_direccion:
            raise PLCError('El formato de la dirección no es correcto: {}'.format(direccion))
        partes_direccion = partes_direccion[0]
        # Quitar '.' del área; si no se ha especificado, asumir "hr" (Modbus)
        if partes_direccion[0] == '':
            area = 'hr'
        else:
            if partes_direccion[0][-1] != '.':
                raise PLCError('Dirección de variable no válida: {}'.format(direccion))
            area = partes_direccion[0][:-1]
            if area[0:2] not in (
                'db', 'mk', ### No implementado: 'pe', 'pa', 'ct', 'tm',
                'co', 'in', 'ir', 'hr'
            ):
                raise PLCError('Area de la variable de dirección "{}" no válida: {}'.format(direccion, area))
        # Si no se ha indicado tipo, asumir que es 'x' (booleano)
        if partes_direccion[1] == '':
            tipo = TipoDatos.booleano
        else:
            try:
                tipo = CARACTER_TIPO_DATOS[partes_direccion[1]]
            except Exception as e:
                raise PLCError('Tipo de datos de dirección "{}" no válido: {}'.format(direccion, partes_direccion[1]))
        # Convertir posición a entero
        try:
            posicion = int(partes_direccion[2])
        except Exception as e:
            raise PLCError('Número de posición de dirección "{}" no válido: {}'.format(direccion, partes_direccion[2]))
        # Para variables booleanas, convertir bit (sin el punto) a entero
        if tipo == TipoDatos.booleano:
            try:
                bit = int(partes_direccion[3][1:])
            except Exception as e:
                raise PLCError('Número de bit de dirección "{}" no válido para variable booleana: {}'.format(direccion, partes_direccion[3]))
            posicion = posicion + (bit / 10 if bit < 10 else bit / 100)
        return (area, tipo, posicion)


    def mapa_variables(self, variables: Dict[str, str]) -> Tuple[Dict[str, Dict[Union[int, float], TipoDatos]], Dict[str, Dict[int, str]], Dict[str, Tuple[int, int, int]]]:
        ''' Devuelve listas de direcciones, tipos y rangos a partir de un mapa
        de direcciones.
        @param variables: diccionario {nombre_variable: tipo+direccion}
            tipo+direccion es una cadena compuesta por uno o dos caracteres que indican
            el tipo de la variable, y un número con la dirección. Tipos admitidos:
                'x' o sin carácter: booleano (la dirección debe ir seguida de un punto y el bit)
                'b': byte (entero sin signo de 8 bits)
                'w': word (entero sin signo de 16 bits)
                'dw': doble word (entero sin signo de 32 bits)
                'i': entero (con signo, 16 bits)
                'di': doble entero (entero con signo de 32 bits)
                'r': real (punto flotante de 32 bits)
                'dr': doble real (punto flotante de 64 bits)
                'qi': cuádruple entero (entero con signo de 64 bits)
                'qw': cuádruple word (entero sin signo de 64 bits)
            Con Siemens, se debe añadir un prefijo, separado por un punto,
            que indica el área a que pertenece la variable:
            dbN = DB número N, mk = marcas, pe = process inputs,
            pa = process outputs, ct = counters, tm = timers
            Con Modbus, se puede usar también un prefijo separado por un punto con el nombre del área:
            co = coils (salidas digitales); in = inputs (entradas digitales);
            ir = input registers (entradas analógicas); hr = holding registers (salidas analógicas).
            Si no se indica el prefijo, se asume 'hr' (holding register).
            Se puede indicar un número a continuación del nombre del área; si se
            especifica, se usa como identificador de dispositivo esclavo Modbus.
            Esto permite acceder a dispositivos que tiene varios "subdipositivos",
            a los que se accede por distintos números de dispositivo Modbus.
        @return (mapa_direcciones, mapa_variables, rango_direcciones):
            mapa_direcciones: dict[area:dict[posicion:tipo]]
            mapa_variables: dict[area:dict[posicion:nombre]]
            rango_direcciones: dict[area:(posicion_min, posicion_max, num_registros)]
        '''
        log.log(DEBUG_CLIENTE_PLC, '-> ClientePLC.mapear_variables(%s)', variables)
        mapa_direcciones = OrderedDict()
        mapa_variables = OrderedDict()
        rango_direcciones = OrderedDict()
        for nombre_variable in variables:
            try:
                (area, tipo, posicion) = self.separar_direccion(variables[nombre_variable])
                if area not in mapa_direcciones:
                    mapa_direcciones[area] = OrderedDict()
                    mapa_variables[area] = OrderedDict()
                mapa_direcciones[area][posicion] = tipo
                mapa_variables[area][posicion] = nombre_variable
            except Exception as e:
                raise PLCError('Dirección de variable no válida: {}'.format(variables[nombre_variable])) from e

        # Calcular el rango de direcciones de cada área, para almacenar el comienzo y número de registros
        # que se necesitan leer en cada una
        for area in mapa_direcciones:
            rango_direcciones[area] = self._rango_posiciones(mapa_direcciones[area])
        return (mapa_direcciones, mapa_variables, rango_direcciones)

    def mapear_variables(self, variables: Dict[str, str], nombre_mapa: Optional[str]=None) -> None:
        ''' Prepara el mapa de direcciones a acceder.
        @param variables: Mismo formato que para función mapa_variables
        @param nombre_mapa (str, opcional): nombre del mapa; se pueden definir varios mapas,
            cada uno con un nombre único, y luego leer solo uno por su nombre. Si no se indica,
            se crea o añaden las variables a un mapa por defecto.
        '''
        log.log(DEBUG_CLIENTE_PLC, '-> ClientePLC.mapear_variables(%s, %s)', variables, nombre_mapa)
        # No inicializamos aquí self._mapa_direcciones, self._mapa_variables ni
        # self._rango_direcciones. El constructor los declara como diccionarios
        # vacíos; este método les añade variables, por lo que se puede usar más
        # de una vez para hacer la unión de varias "zonas" de lectura.
        (mapa_direcciones, mapa_variables, rango_direcciones) = self.mapa_variables(variables)
        if not nombre_mapa in self._mapa_direcciones:
            self._mapa_direcciones[nombre_mapa] = mapa_direcciones
            self._mapa_variables[nombre_mapa] = mapa_variables
            self._rango_direcciones[nombre_mapa] = rango_direcciones
        else:
            self._mapa_direcciones[nombre_mapa].update(mapa_direcciones)
            self._mapa_variables[nombre_mapa].update(mapa_variables)
            self._rango_direcciones[nombre_mapa].update(rango_direcciones)
        log.log(DEBUG_CLIENTE_PLC, '   _mapa_variables=%s', self._mapa_variables)
        log.log(DEBUG_CLIENTE_PLC, '<- ClientePLC.mapear_variables()')

    def leer_valor(self, direccion: Union[int, float, str], tipo: Optional[TipoDatos]=None) -> Any:
        ''' Lee un valor individual de un cierto tipo en la dirección indicada.
        @param direccion: Dirección del valor en el mapa del PLC. Se puede usar un valor numérico (int o float)
            para indicar el offset dento del área por defecto del dispositivo; para leer un bit, se usa un
            número float con direccion.bit. En este caso es necesario pasar también el parámetro "tipo".
            Como alternativa, se puede pasar la dirección como una cadena de texto "area.tipo+direccion",
            en el formato aceptado por "mapear_variables".
        @param tipo: Valor TipoDatos del tipo de dato a leer. Necesario si "direccion" es un valor numérico;
            si "direccion" es de tipo "str", no se usa.
        @return: Valor leido, en el tipo indicado.
        '''
        ###log.log(DEBUG_CLIENTE_PLC, 'ClientePLC.leer_valor(%s,%s,%s)', direccion,tipo,area)
        (area, tipo, direccion, indice_bit) = self._obtener_direccion(direccion, tipo)
        ###TODO: Si se especifica "area", debería escribirse en el área correcta, no asumir DB o HR
        num_registros = self._bytes_tipo_datos[tipo] // self.bytes_por_registro
        respuesta = self.leer_registros(direccion, num_registros)
        return self._bytes_a_valor(respuesta, tipo, indice_bit)


    def leer_array_valores(self, direccion: int, tipo: TipoDatos, numero_valores: int) -> List[Any]:
        ''' Lee un grupo consecutivo de valores del tipo indicado y a partir de la dirección indicada.
            Es más eficiente que leer varios valores individuales con la función leer_valor;
            la lectura de datos del PLC se hace en una sola llamada, y del resultado se
            extraen los valores solicitados.
        @param direccion: Dirección del primer valor en el mapa del PLC.
        @param tipo: Valor TipoDatos del tipo de los datos a leer
        @return: lista con los valores leidos, en el tipo indicado.
        '''
        num_registros = numero_valores * self._bytes_tipo_datos[tipo] // self.bytes_por_registro
        respuesta = self.leer_registros(direccion, num_registros)
        array_valores_leidos = []
        for indice in range(numero_valores):
            indice_byte = indice * self._bytes_tipo_datos[tipo]
            indice_byte_siguiente = indice_byte + self._bytes_tipo_datos[tipo]
            array_valores_leidos.append(self._bytes_a_valor(respuesta[indice_byte:indice_byte_siguiente], tipo))

        return array_valores_leidos

    def _convertir_registros_a_valores(self, registros: bytes, direccion_inicial: int, direccion_final: int, lista_valores: Dict[Union[int, float], TipoDatos]) -> Dict[int, Any]:
        ''' Convierte un array de bytes en un diccionario {direccion: valor}, tomando las
        direcciones y los tipos de los valores de "lista_valores". "direccion_inicial" y
        "direccion_final" son las direcciones reales del primer y último byte del array.
        '''
        log.log(DEBUG_CLIENTE_PLC, '-> _convertir_registros_a_valores(registros=%s, direccion_inicial=%s, direccion_final=%s, lista_valores=%s)', registros, direccion_inicial, direccion_final, lista_valores)
        lista_valores_leidos = {}
        for direccion in lista_valores:
            tipo = lista_valores[direccion]
            if tipo == TipoDatos.booleano:
                (direccion_registro, indice_bit) = self._separar_direccion_bit(direccion)
            else:
                direccion_registro = direccion
                indice_bit = 0
            if direccion_inicial <= direccion_registro <= direccion_final:
                indice_byte = (direccion_registro - direccion_inicial) * self.bytes_por_registro
                indice_byte_siguiente = indice_byte + self._bytes_tipo_datos[tipo]
                lista_valores_leidos[direccion] = self._bytes_a_valor(registros[indice_byte:indice_byte_siguiente], tipo, indice_bit)
        log.log(DEBUG_CLIENTE_PLC, '<- _convertir_registros_a_valores: %s', lista_valores_leidos)
        return lista_valores_leidos

    def leer_lista_valores(self, lista_valores: Dict[Union[int, float], TipoDatos]) -> Dict[int, Any]:
        ''' Lee una lista de valores, cada uno del tipo indicado y en la dirección indicada.
            Es más eficiente que leer varios valores individuales con la función leer_valor;
            la lectura de datos del PLC se hace en el mínimo de llamadas posible, y del resultado
            se extraen los valores solicitados.
        @param lista_valores: diccionario direccion:TipoDatos que describen las direcciones a
            leer y el tipo de dato de cada dirección.
        @return: diccionario direccion:valor con los valores leídos.
        '''
        log.log(DEBUG_CLIENTE_PLC, '   leer_lista_valores(%s)', lista_valores)
        # Para leer en una sola llamada todos los valores, calculamos el o los rangos de registros
        # que hay entre la direcciones más baja a leer y la más alta (si el dispositivo tiene un
        # límite en el número de registros consecutivos que se puede leer, _rango_posiciones
        # devolverá todos los rangos que hay que leer por separado).
        rangos = self._rango_posiciones(lista_valores)
        respuesta = {}
        for rango in rangos:
            registros = self.leer_registros(direccion=rango[self._DIRECCION_MIN], num_registros=rango[self._NUM_REGISTROS])
            respuesta.update(self._convertir_registros_a_valores(registros, rango[self._DIRECCION_MIN], rango[self._DIRECCION_MAX], lista_valores))
        log.log(DEBUG_CLIENTE_PLC, '   %s', respuesta)
        return respuesta

    def leer_mapa_direcciones(self, nombre_mapa: Optional[str]=None, offset: Optional[int]=0) -> Dict[int, Any]:
        ''' Lee del PLC los valores indicados previamente en mapear_variables. El formato devuelto
        es el mismo que para leer_lista_valores.
        @param nombre_mapa (str, opcional): nombre del mapa a leer; si no se
            especifica, se lee del mapa predefinido.
        @param offset (int, opcional): si se especifica, se devuelven los valores leidos de las
            posisciones "tamaño mapa" * offset + "inicio mapa". Es útil si el mapa se repite a
            lo largo del área en posiciones consecutivas; es decir, si el área contiene un array
            con los elementos del mapa repetidos uno tras otro, sin espacio entre ellos.
        @return: diccionario {'area': diccionario {direccion: valor}}
        '''
        log.log(DEBUG_CLIENTE_PLC, '-> leer_mapa_direcciones(%s)', nombre_mapa)
        respuesta = {}
        for area in self._mapa_direcciones[nombre_mapa]:
            respuesta[area] = {}
            for rango in self._rango_direcciones[nombre_mapa][area]:
                log.log(DEBUG_CLIENTE_PLC, '   area=%s, _rango_direcciones[area]=%s', area, rango)
                registros = self.leer_area(
                    area,
                    direccion=rango[self._DIRECCION_MIN] + offset * rango[self._NUM_REGISTROS],
                    num_registros=rango[self._NUM_REGISTROS]
                )
                respuesta[area].update(
                    self._convertir_registros_a_valores(
                        registros, rango[self._DIRECCION_MIN], rango[self._DIRECCION_MAX],
                        self._mapa_direcciones[nombre_mapa][area]
                    )
                )
        log.log(DEBUG_CLIENTE_PLC, '<- leer_mapa_direcciones()')
        return respuesta

    def leer_mapa_variables(self, nombre_mapa: Optional[str]=None, offset: Optional[int]=0) -> Dict[str, Any]:
        ''' Lee del PLC los valores indicados previamente en mapear_variables.
        El formato devuelto es un diccionario con el valor de cada variable;
        el área de la que se ha leído se descarta, y se devuelven todas las
        variables reunidas en un solo diccionario.
        @param nombre_mapa (str, opcional): nombre del mapa a leer; si no se
            especifica, se lee del mapa predefinido.
        @param offset (int, opcional): si se especifica, se devuelven los valores leidos de las
            posisciones "tamaño mapa" * offset + "inicio mapa". Es útil si el mapa se repite a
            lo largo del área en posiciones consecutivas; es decir, si el área contiene un array
            con los elementos del mapa repetidos uno tras otro, sin espacio entre ellos.
        @return: diccionario {nombre_variable: valor}
        '''
        log.log(DEBUG_CLIENTE_PLC, '-> leer_mapa_variables(%s)', nombre_mapa)
        respuesta = {}
        valores = self.leer_mapa_direcciones(nombre_mapa, offset)
        for area in valores:
            respuesta.update(
                {self._mapa_variables[nombre_mapa][area][posicion]:valores[area][posicion]
                for posicion in self._mapa_variables[nombre_mapa][area]}
            )
        log.log(DEBUG_CLIENTE_PLC, '<- leer_mapa_variables()')
        return respuesta

    def _obtener_direccion(self, direccion: Union[int, float, str], tipo: Optional[TipoDatos]=None) -> Tuple[str, TipoDatos, int, int]:
        ''' Si direccion es de tipo "str", la separa en área, tipo y dirección.
        Si no, devuelve la dirección y el tipo que se pasan como parámetro.
        En ambos casos, la dirección se devuelve en forma de entero, separando el índice de bit
        (si se ha especificado) que se devuelve aparte,
        '''
        # Si la dirección se pasa como una cadena de texto, separarla en área, tipo y dirección
        if isinstance(direccion, str):
            (area, tipo_str, direccion) = self.separar_direccion(direccion)
            tipo = tipo_str if tipo_str else tipo
        else:
            area = ''
        # Asegurarse que el tipo se ha indicado, bien en la dirección str, o en el parámetro "tipo"
        if not tipo:
            raise PLCError('No se ha indicado el tipo de dato')
        # Para acceder a bits, separamos la dirección (parte entera) del índice del bit (primer decimal).
        # Se podría usar math.modf, pero devuelve dos números reales; usamos una alternativa que devuelve dos enteros.
        if tipo == TipoDatos.booleano:
            (direccion_int, indice_bit) = self._separar_direccion_bit(direccion)
        else:
            direccion_int = int(direccion)
            indice_bit = 0
        return (area, tipo, direccion_int, indice_bit)

    def escribir_valor(self, valor: Any, direccion: Union[int, float, str], tipo: Union[TipoDatos, None] = None) -> None:
        ''' Escribe en el PLC un valor del tipo indicado en la dirección indicada.
        @param valor: valor a escribir
        @param direccion: Dirección del valor en el mapa del PLC. Se puede usar un valor numérico (int o float)
            para indicar el offset dento del área por defecto del dispositivo; para escribir un bit, se usa un
            número float con direccion.bit. En este caso es necesario pasar también el parámetro "tipo".
            Como alternativa, se puede pasar la dirección como una cadena de texto "area.tipo+direccion",
            en el formato aceptado por "mapear_variables".
        @param tipo: Valor TipoDatos del tipo de dato a escribir. Necesario si "direccion" es un valor numérico;
            si "direccion" es de tipo "str", no se usa.
        '''
        ###log.log(DEBUG_CLIENTE_PLC, 'ClientePLC.escribir_valor(%s,%s,%s,%s)', valor,direccion,tipo,area)
        (area, tipo, direccion, indice_bit) = self._obtener_direccion(direccion, tipo)
        ###TODO: Si se especifica "area", debería escribirse en el área correcta, no asumir DB o HR
        datos = self._valor_a_bytes(valor, tipo, indice_bit)
        if tipo == TipoDatos.booleano:
            # Leer el valor del registro completo que contiene el bit, para
            # combinarlo con el bit a escribir y así no modificar los valores
            # del resto de bits
            registro_actual = self.leer_registros(direccion, num_registros=1)
            # Las operaciones bitwise no se pueden aplicar a byte arrays (son inmutables);
            # convertimos los valores a entero (lo que permite usar todos los bits del registro,
            # sea de 8 o 16 bits), los combinamos, y luego convertirlo de vuelta a byte array
            bits = int.from_bytes(registro_actual, byteorder='big')
            bits_escribir = int.from_bytes(datos, byteorder='big')
            bits_resultado = (bits & ~(1 << indice_bit)) | bits_escribir
            datos = bits_resultado.to_bytes(self.bytes_por_registro, byteorder='big', signed=False)
        num_registros = self._bytes_tipo_datos[tipo] // self.bytes_por_registro
        self.escribir_registros(datos, direccion, num_registros)


    def leer_registros(self, direccion: int, num_registros: int=1) -> bytes:
        ''' Lee el número de registros (palabras de tamaño word o byte, dependiendo del sistema)
        a partir de la dirección especificada.
        Cada clase derivada debe implementar su propio método leer_registros, ya que la forma
        de acceder al PLC depende del fabricante.
        @param direccion: Dirección inicial en el mapa del PLC desde la que leer.
        @param num_registros: Cantidad de registros a leer.
        @return: Byte array con los valores leídos. Si el tamaño de registro es 1 byte,
            se devuelven num_registros bytes; si el tamaño del registro es 2 bytes,
            se devuelven num_registros * 2 bytes.
        '''
        # Redefinir en clases derivadas; cada tipo de PLC usa un método distinto
        raise NotImplementedError()

    def leer_area(self, area: str, direccion: int, num_registros: int, id_adicional: Optional[int]=None) -> bytes:
        ''' Lee el número de registros (palabras de tamaño word o byte, dependiendo del
        tipo de dispositivo) del área indicada del PLC, a partir de la dirección indicada.
        @param area: Nombre del área de la que leer. Los valores válidos dependen del tipo
            de PLC.
        @param direccion: Dirección inicial en el mapa del PLC desde la que leer.
        @param num_registros: Cantidad de registros a leer.
        @param id_adicional: identificador adicional del área o esclavo en que escribir.
            Se usa para tipos de áreas múltiples (DB) o dispositivos que tienen múltiples
            esclavos (Modbus)
        @return: Byte array con los valores leídos; se devuelven num_registros bytes.
        '''
        # Redefinir en clases derivadas; cada tipo de PLC usa un método distinto
        raise NotImplementedError()

    def escribir_registros(self, valores: bytes, direccion: int, num_registros: int=1):
        ''' Escribe en el PLC los valores en los registros a partir del indicado.
        @param valores: byte array con los valores a escribir. La longitud de valores
            debe ser igual a num_registros * tamaño registro.
        @param direccion: Dirección inicial en el mapa del PLC en que escribir
        @param num_registros: Cantidad de registros a escribir.
        '''
        # Redefinir en clases derivadas; cada tipo de PLC usa un método distinto
        raise NotImplementedError()

    def escribir_area(self, valores: bytes, area: str, direccion: int, num_registros: Optional[int]=1, id_adicional: Optional[int]=None):
        ''' Escribe el número de registros (palabras de tamaño word o byte, dependiendo
        del tipo de dispositivo) en el área indicada del PLC, a partir de la dirección
        indicada.
        @param valores: byte array con los valores a escribir. La longitud de valores
            debe ser igual a num_registros * tamaño registro.
        @param area: Nombre del área en la que escribir. Los valores válidos dependen del tipo
            de PLC.
        @param direccion: Dirección inicial en el mapa del PLC en la que escribir.
        @param num_registros: Cantidad de registros a escribir.
        @param id_adicional: identificador adicional del área o esclavo en que escribir.
            Se usa para tipos de áreas múltiples (DB) o dispositivos que tienen múltiples
            esclavos (Modbus)
        '''
        # Redefinir en clases derivadas; cada tipo de PLC usa un método distinto
        raise NotImplementedError()


#############################################################################

class ParametroS7(IntEnum):
    ''' Codigos de los posibles parámetros para las funciones leer_parametro
    y cambiar_parametro. Ver descripción detallada en cambiar_parametro
    '''
    LocalPort = 1
    RemotePort = 2
    PingTimeout = 3
    SendTimeout = 4
    RecvTimeout = 5
    WorkInterval = 6
    SrcRef = 7
    DstRef = 8
    SrcTSap = 9
    PDURequest = 10
    MaxClients = 11
    BSendTimeout = 12
    BRecvTimeout = 13
    RecoveryTime = 14
    KeepAliveTime = 15

# Códigos de error devueltos por las llamadas a las funciones snap7
# s7_client_errors = {
#     0x00100000: 'errNegotiatingPDU',
#     0x00200000: 'errCliInvalidParams',
#     0x00300000: 'errCliJobPending',
#     0x00400000: 'errCliTooManyItems',
#     0x00500000: 'errCliInvalidWordLen',
#     0x00600000: 'errCliPartialDataWritten',
#     0x00700000: 'errCliSizeOverPDU',
#     0x00800000: 'errCliInvalidPlcAnswer',
#     0x00900000: 'errCliAddressOutOfRange',
#     0x00A00000: 'errCliInvalidTransportSize',
#     0x00B00000: 'errCliWriteDataSizeMismatch',
#     0x00C00000: 'errCliItemNotAvailable',
#     0x00D00000: 'errCliInvalidValue',
#     0x00E00000: 'errCliCannotStartPLC',
#     0x00F00000: 'errCliAlreadyRun',
#     0x01000000: 'errCliCannotStopPLC',
#     0x01100000: 'errCliCannotCopyRamToRom',
#     0x01200000: 'errCliCannotCompress',
#     0x01300000: 'errCliAlreadyStop',
#     0x01400000: 'errCliFunNotAvailable',
#     0x01500000: 'errCliUploadSequenceFailed',
#     0x01600000: 'errCliInvalidDataSizeRecvd',
#     0x01700000: 'errCliInvalidBlockType',
#     0x01800000: 'errCliInvalidBlockNumber',
#     0x01900000: 'errCliInvalidBlockSize',
#     0x01A00000: 'errCliDownloadSequenceFailed',
#     0x01B00000: 'errCliInsertRefused',
#     0x01C00000: 'errCliDeleteRefused',
#     0x01D00000: 'errCliNeedPassword',
#     0x01E00000: 'errCliInvalidPassword',
#     0x01F00000: 'errCliNoPasswordToSetOrClear',
#     0x02000000: 'errCliJobTimeout',
#     0x02100000: 'errCliPartialDataRead',
#     0x02200000: 'errCliBufferTooSmall',
#     0x02300000: 'errCliFunctionRefused',
#     0x02400000: 'errCliDestroying',
#     0x02500000: 'errCliInvalidParamNumber',
#     0x02600000: 'errCliCannotChangeParam',
# }
#
# isotcp_errors = {
#     0x00010000: 'errIsoConnect',
#     0x00020000: 'errIsoDisconnect',
#     0x00030000: 'errIsoInvalidPDU',
#     0x00040000: 'errIsoInvalidDataSize',
#     0x00050000: 'errIsoNullPointer',
#     0x00060000: 'errIsoShortPacket',
#     0x00070000: 'errIsoTooManyFragments',
#     0x00080000: 'errIsoPduOverflow',
#     0x00090000: 'errIsoSendPacket',
#     0x000A0000: 'errIsoRecvPacket',
#     0x000B0000: 'errIsoInvalidParams',
#     0x000C0000: 'errIsoResvd_1',
#     0x000D0000: 'errIsoResvd_2',
#     0x000E0000: 'errIsoResvd_3',
#     0x000F0000: 'errIsoResvd_4',
# }
#
# tcp_errors = {
#     0x00000001: 'evcServerStarted',
#     0x00000002: 'evcServerStopped',
#     0x00000004: 'evcListenerCannotStart',
#     0x00000008: 'evcClientAdded',
#     0x00000010: 'evcClientRejected',
#     0x00000020: 'evcClientNoRoom',
#     0x00000040: 'evcClientException',
#     0x00000080: 'evcClientDisconnected',
#     0x00000100: 'evcClientTerminated',
#     0x00000200: 'evcClientsDropped',
#     0x00000400: 'evcReserved_00000400',
#     0x00000800: 'evcReserved_00000800',
#     0x00001000: 'evcReserved_00001000',
#     0x00002000: 'evcReserved_00002000',
#     0x00004000: 'evcReserved_00004000',
#     0x00008000: 'evcReserved_00008000',
# }

class ClientePLCSiemens(ClientePLC):
    ''' Objeto cliente para comunicación con PLCs de Siemens serie 7.
        Internamente se usan funciones de la librería Snap7, que debe estar
        accesible en forma de DLL "snap7.dll" en el mismo directorio del ejecutable,
        o en uno de los directorios incluidos en el path de librerías del sistema.
        S7 300/400/WinAC: Compatibilidad total, todas las funciones disponibles.
        S7 1200/1500 CPU: Compatibilidad parcial: la librería usa el protocolo "base",
        funcionando como un HMI (solo se pueden hacer transferencias básicas de datos):
            DB Read/Write, EB Read/Write, AB Read/Write, MK Read/Write, Read SZL,
            Multi Read/Write.
        Las funciones de directorio, fecha y hora, control, seguridad, carga de bloques,
        TM Read/Write y CT Read/Write no están disponibles.
        Además, con los S7 1500 solo puede accederse a DB globales. Y los DB deben estar
        configurados así:
            - "Atributos": desmarcar "Acceso optimizado al bloque"
        Y en la configuración de la CPU, en "Protección":
            - "Nivel de acceso": Acceso completo (sin protección)
            - "Mecanismos de conexión": marcar "Permitir acceso vía comunicación PUT/GET
            del interlocutor remoto"
    '''
    class __TipoDatoS7(IntEnum):
        ''' Tipos de datos usados en libreria snap7. Los valores corresponden al parámetro "wordlen" para leer/escribir cada tipo de datos en las funciones Cli_ReadArea y Cli_WriteArea
        '''
        Bit = 0x01
        Byte = 0x02
        Word = 0x04
        DWord = 0x06
        Real = 0x08
        Counter = 0x1C
        Timer = 0x1D
    # Tipo "ctype" equivalente para cada tipo de datos S7
    __ctype_equivalente_tipo_s7 = {
        __TipoDatoS7.Bit: ctypes.c_char,  ###c_int8,
        __TipoDatoS7.Byte: ctypes.c_char, ###c_int8,
        __TipoDatoS7.Word: ctypes.c_int16,
        __TipoDatoS7.DWord: ctypes.c_int32,
        __TipoDatoS7.Real: ctypes.c_int32,
        __TipoDatoS7.Counter: ctypes.c_int16,
        __TipoDatoS7.Timer: ctypes.c_int16,
    }
    # Tamaño en bytes de cada tipo de datos S7
    __longitud_tipo_s7 = {
        __TipoDatoS7.Bit: 1,
        __TipoDatoS7.Byte: 1,
        __TipoDatoS7.Word: 2,
        __TipoDatoS7.DWord: 4,
        __TipoDatoS7.Real: 4,
        __TipoDatoS7.Counter: 2,
        __TipoDatoS7.Timer: 2,
    }
    class __AreaS7(IntEnum):
        ''' Areas accesibles
        '''
        PE = 0x81
        PA = 0x82
        MK = 0x83
        DB = 0x84
        CT = 0x1C
        TM = 0x1D
    # Nombres de las áreas en formato texto (los usados en los mapeados de
    # variables)
    __nombre_area = {
        'pe': __AreaS7.PE,
        'pa': __AreaS7.PA,
        'mk': __AreaS7.MK,
        'db': __AreaS7.DB,
        'ct': __AreaS7.CT,
        'tm': __AreaS7.TM
        }
    # Tipo de los datos de cada area
    __tipo_datos_area = {
        'pe': __TipoDatoS7.Byte,
        'pa': __TipoDatoS7.Byte,
        'mk': __TipoDatoS7.Bit,
        'db': __TipoDatoS7.Byte,
        'ct': __TipoDatoS7.Counter,
        'tm': __TipoDatoS7.Timer
        }
    # Tipo "ctype" de los parámetros disponibles en las funciones
    # leer_parametro, _cambiar_parametro
    __tipo_parametro_s7 = {
        ParametroS7.LocalPort: ctypes.c_uint16,
        ParametroS7.RemotePort: ctypes.c_uint16,
        ParametroS7.PingTimeout: ctypes.c_int32,
        ParametroS7.SendTimeout: ctypes.c_int32,
        ParametroS7.RecvTimeout: ctypes.c_int32,
        ParametroS7.WorkInterval: ctypes.c_int32,
        ParametroS7.SrcRef: ctypes.c_uint16,
        ParametroS7.DstRef: ctypes.c_uint16,
        ParametroS7.SrcTSap: ctypes.c_uint16,
        ParametroS7.PDURequest: ctypes.c_int32,
        ParametroS7.MaxClients: ctypes.c_int32,
        ParametroS7.BSendTimeout: ctypes.c_int32,
        ParametroS7.BRecvTimeout: ctypes.c_int32,
        ParametroS7.RecoveryTime: ctypes.c_uint32,
        ParametroS7.KeepAliveTime: ctypes.c_uint32,
    }

    # Librería snap7. Habrá una sola instancia de la librería, por lo
    # que definimos una variable de clase.
    __snap7dll = None


    def __init__(self, ip: Optional[str]=None, puerto: Optional[int]=None, rack: Optional[int]=None, slot: Optional[int]=None):
        ''' Constructor. Crea el objeto para comunicar con el PLC, pero no
        intenta conectar con él.
        @param ip (str, opcional): IPv4 del autómata ('a.b.c.d'). Se puede indicar aquí
            o en el método conectar().
        @param puerto (int, opcional): por defecto 102
        @param rack (int, opcional): por defecto 0
        @param slot (int, opcional): por defecto 1
        '''
        # Los PLC de Siemens usan por defecto el puerto 102 (RFC1006, ISO-on-TCP)
        if puerto is None:
            puerto = 102
        if rack is None:
            rack = 0
        if slot is None:
            slot = 1

        log.log(DEBUG_CLIENTE_PLC, '-> ClientePLCSiemens.__init__(ip=%s, puerto=%s, rack=%s, slot=%s)', ip, puerto, rack, slot)
        super().__init__(ip, puerto)
        # Siemens usa valores big-endian
        self.orden_bytes = '>'
        # Las funciones que leen datos de una BD necesitan el número de la BD.
        # Lo inicializamos a None para indicar que no se ha especificado todavía.
        self.numero_db = None
        self.rack = rack
        self.slot = slot

        # Inicialización de la librería Snap7: se hace una sola vez.
        # Si no se encuentra la librería, se genera una excepción.
        self.__objetoS7 = None
        if not ClientePLCSiemens.__snap7dll:
            try:
                # Si el programa se empaqueta con pyinstaller --onefile, hay que añadir
                # el directorio temporal sys._MEIPASS al path para cargar de ahí la DLL.
                # Si no está definido sys._MEIPASS, usamos el directorio actual.
                if platform.system().lower().startswith('win'):
                    directorio_trabajo = getattr(sys, '_MEIPASS', os.getcwd())
                    win32api.SetDllDirectory(directorio_trabajo)
                # Si find_library no encuentra la librería DLL, intentamos usar el nombre
                # de la librería (sin .dll) para cargarla del directorio de trabajo.
                ubicacion_libreria = ctypes.util.find_library('snap7')
                if not ubicacion_libreria:
                    ubicacion_libreria = 'snap7'
                log.log(DEBUG_CLIENTE_PLC, '   ubicación libreria=%s', ubicacion_libreria)
                ClientePLCSiemens.__snap7dll = ctypes_cdll(ubicacion_libreria)
                log.log(DEBUG_CLIENTE_PLC, '   __snap7dll=%s', ClientePLCSiemens.__snap7dll)
            except Exception as e:
                raise PLCErrorLibreria('Error al cargar la librería Snap7:\n{}'.format(e))

        # Objeto cliente Snap7, que se pasa como parámetro a las funciones
        # de la librería. (El valor es un handle al objeto.)
        self.__snap7dll.Cli_Create.argtypes = []
        self.__snap7dll.Cli_Create.restype = CTYPES_HANDLE
        self.__objetoS7 = self.__snap7dll.Cli_Create()
        log.log(DEBUG_CLIENTE_PLC, '   self.__objetoS7=%s', self.__objetoS7)
        log.log(DEBUG_CLIENTE_PLC, '<- ClientePLCSiemens.__init__()')

    def __del__(self):
        # Destruimos el objeto Snap7. Si está conectado, se desconecta automáticamente.
        # El handle al objeto se pasa por referencia, para que la función lo ponga a NULL;
        # en Python, NULL es igual a None.
        if self.__snap7dll and self.__objetoS7:
            self.__snap7dll.Cli_Destroy.argtypes = [ctypes.POINTER(CTYPES_HANDLE)]
            self.__snap7dll.Cli_Destroy.restype = ctypes.c_int
            # Usamos un typecast para evitar error "TypeError: byref() argument must be a ctypes instance, not 'int'"
            self.__snap7dll.Cli_Destroy(ctypes.byref(CTYPES_HANDLE(self.__objetoS7)))


    def __descripcion_error(self, codigo_error: int) -> str:
        ''' Devuelve el mensaje de error que corresponde al código de error snap7 indicado.
        @param codigo_error: Código de error devuelto por la llamada a una función de la
            librería snap7.
        @return Cadena de texto con el mensaje correspondiente al código pasado.
            Si se produce un error al recuperar el mensaje, se devuelve una descripción del
            error que se ha producido.
        '''
        longitud_texto = 1024
        try:
            texto = ctypes.create_string_buffer(longitud_texto)
            self.__snap7dll.Cli_ErrorText.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
            self.__snap7dll.Cli_ErrorText.restype = ctypes.c_int
            self.__snap7dll.Cli_ErrorText(codigo_error, texto, longitud_texto)
            # El mensaje viene como array de bytes; asumimos que la codificación es Windows ANSI
            return texto.value.decode('cp1252')
        except Exception as e:
            return str(e)

    def __generar_excepcion(self, codigo_error: int, mensaje_error: Optional[str]=None) -> NoReturn:
        ''' Comprueba el código de error devuelto por la librería Snap7, y
        genera la excepción que corresponda: PLCErrorSiemens si es un error
        devuelto por el PLC, PLCErrorComunicacion si es un error de TCP/IP,
        o PLCError para otros errores genéricos.
        El código está compuesto por tres dígitos hex (12 bits) con el error S7,
        un dígito (4 bits) con el error ISO TCP, y cuatro dígitos (16 bits) con
        el error TCP/IP dependiente del sistema.
        Esta función asume que si los tres primeros dígitos no son cero, es un
        error del PLC; si alguno del resto de dígitos no es cero, es un error
        de comunicación; y si todos son cero, es otro tipo de error, en cuyo
        caso se genera un PLCError con "mensaje_error" como descripción.
        '''
        # Separar las tres partes del código
        error_plc = codigo_error & 0xFFF00000
        error_iso_tcp = codigo_error & 0x000F0000
        error_tcp_ip = codigo_error & 0x0000FFFF
        if error_plc:
            raise PLCErrorSiemens(codigo_error, self.__descripcion_error(codigo_error))
        elif error_iso_tcp or error_tcp_ip:
            if self.desconectar_si_error_comunicacion:
                try:
                    self.desconectar()
                    time.sleep(self.pausa_entre_accesos)
                except Exception:
                    pass
            raise PLCErrorComunicacion(self.__descripcion_error(codigo_error))
        else:
            raise PLCError(mensaje_error)


    def cambiar_parametro(self, codigo_parametro: ParametroS7, valor: int) -> None:
        ''' Cambia el valor de uno de los parámetros internos del objeto Snap7.
        Normalmente no debe ser necesario modificar estos parámetros, la
        librería Snap7 tiene valores por defecto bien ajustados.
        @param codigo_parametro: Uno de los valores ParametroS7 que indica
        el parámetro a cambiar:
            LocalPort: puerto del socket local (SERVIDOR)
            RemotePort: puerto del socket remoto
            PingTimeout: timeout del ping al servidor; 0 = desactivar ping
            SendTimeout: timeout del socket al enviar
            RecvTimeout: timeout del socket al recibir
            WorkInterval: intervalo del worker del socket (SERVIDOR)
            SrcRef: Referencia del origen ISOTcp
            DstRef: Referencia del destino ISOTcp
            SrcTSap: TSAP del origen ISOTcp
            PDURequest: longitud inicial de la solicitud PDU
            MaxClients: máximo número de clientes permitidos (SERVIDOR)
            BSendTimeout: timeout para completar la secuencia BSend (PARTNER)
            BRecvTimeout: timeout para completar la secuencia BRecv (PARTNER)
            RecoveryTime: tiempo de recuperación de una desconexión (PARTNER)
            KeepAliveTime: tiempo para mantener el PLC partenr vivo (PARTNER)
        Nota: los parámetros marcados como SERVIDOR o PARTNER no se pueden
            usar en las funciones de un cliente.
        @param valor: Nuevo valor del parámetro.
            Los parámetros LocalPort, RemotePort, SrcRef, DstRef y SrcTSap
            admiten valores enteros sin signo de 16 bits (entre 0 y 65535).
            El resto admiten valores enteros de 32 bits: RecoveryTime y
            KeepAliveTime sin signo, los demás con signo.
        Si se produce un error al cambiar el parámetro, se genera una excepción
        PLCErrorSiemens o PLCErrorComunicacion, según el motivo del error.
        '''
        log.log(DEBUG_CLIENTE_PLC, '-> ClientePLCSiemens.cambiar_parametro(%s, %s)', codigo_parametro, valor)
        tipo = ClientePLCSiemens.__tipo_parametro_s7[codigo_parametro]
        mensaje_resultado = None
        try:
            if THREADSAFE:
                self.mutex_acceso.acquire()
            # Definimos el tipo del último parámetro de Cli_SetParam según el tipo del dato que se le pasa
            self.__snap7dll.Cli_SetParam.argtypes = [
                CTYPES_HANDLE, ctypes.c_int, ctypes.POINTER(tipo)
            ]
            self.__snap7dll.Cli_SetParam.restype = ctypes.c_int
            codigo_resultado = self.__snap7dll.Cli_SetParam(
                self.__objetoS7, codigo_parametro, ctypes.byref(tipo(valor))
            )
            time.sleep(self.pausa_entre_accesos)
        except Exception as e:
            codigo_resultado = 0
            mensaje_resultado = 'ClientePLCSiemens.cambiar_parametro: {}: {}'.format(e.__class__.__name__, e)
        finally:
            if THREADSAFE:
                self.mutex_acceso.release()
        # Si se ha producido un error, generamos una excepción con el mensaje de error que corresponde al código de error devuelto
        if codigo_resultado or mensaje_resultado:
            self.__generar_excepcion(codigo_resultado, mensaje_resultado)

    def leer_parametro(self, codigo_parametro: ParametroS7) -> Union[int, None]:
        ''' Devuelve el valor de uno de los parámetros internos del objeto
        Snap7.
        @param codigo_parametro: Uno de los valores ParametroS7 que indica
            el parámetro a leer. Ver cambiar_parametro
        @return Resultado: Valor del parámetro leído.
        Si se produce un error al leer el parámetro, se genera una excepción
        PLCErrorSiemens o PLCErrorComunicacion, según el motivo del error.
        '''
        log.log(DEBUG_CLIENTE_PLC, '-> ClientePLCSiemens.leer_parametro(%s)', codigo_parametro)
        mensaje_resultado = None
        valor = None
        try:
            if THREADSAFE:
                self.mutex_acceso.acquire()
            tipo = ClientePLCSiemens.__tipo_parametro_s7[codigo_parametro]
            valor = tipo(0)
            self.__snap7dll.Cli_GetParam.argtypes = [
                CTYPES_HANDLE, ctypes.c_int, ctypes.POINTER(tipo)
            ]
            self.__snap7dll.Cli_GetParam.restype = ctypes.c_int
            codigo_resultado = self.__snap7dll.Cli_GetParam(
                self.__objetoS7, codigo_parametro, ctypes.byref(valor)
            )
            time.sleep(self.pausa_entre_accesos)
        except Exception as e:
            codigo_resultado = 0
            mensaje_resultado = 'ClientePLCSiemens.leer_parametro: {}: {}'.format(e.__class__.__name__, e)
        finally:
            if THREADSAFE:
                self.mutex_acceso.release()
        if codigo_resultado or mensaje_resultado:
            self.__generar_excepcion(codigo_resultado, mensaje_resultado)
        else:
            return valor


    def conectar(self, ip: Optional[str]=None, rack: Optional[int]=None, slot: Optional[int]=None) -> None:
        ''' Abre la conexión TCP con el autómata.
        Si se pasa alguno de (o todos) los valores "ip", "rack" y "slot", se usarán al conectar;
        si no, se usarán los valores asignados en el constructor.
        Si no se ha asignado un valor a la IP ni aquí ni en el constructor, se generará una excepción ValueError.
        '''
        log.log(DEBUG_CLIENTE_PLC, '-> ClientePLCSiemens.conectar(%s, %s, %s)', ip, rack, slot)
        # Si ya está conectado: si es al mismo autómata (misma ip, rack y slot)
        # y la conexión está funcionando (hay respuesta a un ping) no hacer nada.
        # Si no, desconectar antes de conectar al nuevo autómata.
        if self._conectado:
            if (ip is None or self.ip == ip) and (rack is None or self.rack == rack) and (slot is None or self.slot == slot):
                if ping2(self.ip, intentos=3):
                    return
            self.desconectar()
        if ip is not None:
            self.ip = ip
        if rack is not None:
            self.rack = rack
        if slot is not None:
            self.slot = slot
        # Comprobar la IP, generando excepción ValueError si no es válida
        ipaddress.ip_address(self.ip)
        log.log(DEBUG_CLIENTE_PLC, '   Formato IP correcto')

        # Por defecto está en modo PG = 1 (Programming Mode, el que da más posibilidades).
        # Se puede configurar la conexión en modo OP = 2 (el más adecuado para un HMI) o
        # en modo S7 Basic = 3, con la llamada:
        #    codigo_resultado = self.__snap7dll.Cli_SetConnectionType(self.__objetoS7, 2)
        # Antes de intentar la conexión, fijamos el puerto remoto del PLC,
        # si hay que usar uno que no es el estándar (puerto TCP 102).
        ### Por ahora, ignoramos el valor devuelto
        if self.puerto is not None and self.puerto != 102:
            self.cambiar_parametro(ParametroS7.RemotePort, self.puerto)
            log.log(DEBUG_CLIENTE_PLC, '   Configurado puerto')
            time.sleep(self.pausa_entre_accesos)
        # Valor por defecto ping timeout=c_long(750)
        #self.cambiar_parametro(ParametroS7.PingTimeout, 1500)
        # Valor por defecto send timeout=c_long(10)
        #self.cambiar_parametro(ParametroS7.SendTimeout, 50)
        # Valor por defecto recv timeout=c_long(3000)
        #self.cambiar_parametro(ParametroS7.RecvTimeout, 6000)

        log.log(DEBUG_CLIENTE_PLC, '   Conectando a %s rack %s slot %s', self.ip, self.rack, self.slot)
        mensaje_resultado = None
        try:
            if THREADSAFE:
                self.mutex_acceso.acquire()
            ###self.__snap7dll.Cli_ConnectTo.argtypes = [pointer(S7Object),ctypes.c_char_p,ctypes.c_int,ctypes.c_int]
            ###S7Object = ctypes.c_void_p
            self.__snap7dll.Cli_ConnectTo.argtypes = [
                CTYPES_HANDLE, ctypes.c_char_p, ctypes.c_int, ctypes.c_int
            ]
            self.__snap7dll.Cli_ConnectTo.restype = ctypes.c_int
            codigo_resultado = self.__snap7dll.Cli_ConnectTo(
                self.__objetoS7, ctypes.c_char_p(self.ip.encode('latin-1')),
                ctypes.c_int(self.rack), ctypes.c_int(self.slot)
            )
            # La llamada a la función Cli_ConnectTo no genera excepción si falla, pero devuelve un código de resultado != 0
            if not codigo_resultado:
                log.log(DEBUG_CLIENTE_PLC, '   Conectado')
                self._conectado = True
                log.info('Conectado al dispositivo Siemens: IP=%s, rack=%s, slot=%s', self.ip, self.rack, self.slot)
            time.sleep(self.pausa_entre_accesos)
        except Exception as e:
            codigo_resultado = 0
            mensaje_resultado = '{} al conectar al PLC con ip={}, rack={}, slot={}: {}'.format(e.__class__.__name__, self.ip, self.rack, self.slot, e)
        finally:
            if THREADSAFE:
                self.mutex_acceso.release()
        if codigo_resultado or mensaje_resultado:
            self.__generar_excepcion(codigo_resultado, mensaje_resultado)
        log.log(DEBUG_CLIENTE_PLC, '<- ClientePLCSiemens.conectar()')


    def desconectar(self) -> None:
        log.log(DEBUG_CLIENTE_PLC, '-> ClientePLCSiemens.desconectar()')
        try:
            if THREADSAFE:
                self.mutex_acceso.acquire()
            self.__snap7dll.Cli_Disconnect.argtypes = [CTYPES_HANDLE]
            self.__snap7dll.Cli_Disconnect.restype = ctypes.c_int
            # Ignoramos el valor devuelto, siempre será 0
            self.__snap7dll.Cli_Disconnect(self.__objetoS7)
            self._conectado = False
            log.info('Desconectado del dispositivo Siemens: IP=%s, rack=%s, slot=%s', self.ip, self.rack, self.slot)
            time.sleep(self.pausa_entre_accesos)
        finally:
            if THREADSAFE:
                self.mutex_acceso.release()
        log.log(DEBUG_CLIENTE_PLC, '<- ClientePLCSiemens.desconectar()')

    def leer_area(self, area: Union[int, str], direccion: int, num_registros: int, id_adicional: Optional[int]=None) -> bytes:
        ''' Lee bytes de una de las áreas del PLC, a partir de la dirección indicada.
        @param area: Nombre del área de la que leer. Posibles valores:
            'pe': entradas de proceso
            'pa': salidas de proceso
            'mk': marcas
            'dbN': DB número N (N = entero positivo). Alternativa: usar solo 'db'
                e indicar el número del DB en el parámetro id_adicional.
            'ct': contadores
            'tm': timers
            Si "area" es numérico, se asume que el área es "DB" + número pasado.
        @param direccion: Dirección del valor en el área del PLC. Si el área es 'mk',
            debe expresarse en bits.
        @param num_registros: Cantidad de registros a leer.
        @param id_adicional: número del DB, si se lee del área "db". No hay que indicarlo
            si se especifica el número del DB en el nombre del área.
        @return: Byte array con los valores leídos; se devuelven num_registros bytes.

        NOTA: Aunque el tamaño de los paquetes de datos que se leen o escriben al PLC
        está limitado, la librería Snap7 se encarga de "trocear" los paquetes que
        excedan el tamaño adecuado para el PLC concreto al que se está accediendo.
        '''
        log.log(DEBUG_CLIENTE_PLC, '-> ClientePLCSiemens.leer_area(%s,%s,%s,%s)', area, direccion, num_registros, id_adicional)

        # Si el área es numérica, se asume que es el DB con número indicado.
        if isinstance(area, int):
            numero_db = area
            area = 'db'
        else:
            area = area.lower()
            # Si el área empieza por "db", debe llevar a continuación el número del DB,
            # o bien debe venir el número del DB en el parámetro id_adicional.
            if area.startswith('db'):
                try:
                    numero_db = int(area[2:])
                    area = 'db'
                except Exception as e:
                    if id_adicional is None:
                        raise PLCError('Número del DB no indicado en área ({}) ni en parámetro adicional ({}): {}'.format(area, id_adicional, e))
                    numero_db = id_adicional
            else:
                numero_db = 0

        # Creamos un buffer para almacenar los bytes necesarios
        tipo_datos_area = ClientePLCSiemens.__tipo_datos_area[area]
        num_bytes = ClientePLCSiemens.__longitud_tipo_s7[tipo_datos_area] * num_registros
        datos = (ctypes.c_char * num_bytes)()    # Buffer para almacenar los bytes que lee la función
        mensaje_resultado = None
        try:
            if THREADSAFE:
                log.log(DEBUG_CLIENTE_PLC, '  mutex: %s [%s]', self.mutex_acceso, numero_db)
                if not self.mutex_acceso.acquire(timeout=self.timeout_acceso):
                    raise Exception('No se ha conseguido acceso exclusivo para leer')
            if self.conectar_automaticamente and not self._conectado:
                self.conectar()
                time.sleep(self.pausa_entre_accesos)
            # Llamada a la función que lee del PLC. Parámetros:
            #     Area, DBNumber (ignorado si area no es DB), Start, Amount, WordLen, *pData
            log.log(DEBUG_CLIENTE_PLC,
                '   Cli_ReadArea(__objetoS7, %s, %s, %s, %s, %s, datos)',
                ClientePLCSiemens.__nombre_area[area],
                numero_db, direccion, num_registros, tipo_datos_area
            )
            self.__snap7dll.Cli_ReadArea.argtypes = [
                CTYPES_HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, ctypes.c_char_p
            ]
            self.__snap7dll.Cli_ReadArea.restype = ctypes.c_int
            hora_comienzo_lecturas = time.perf_counter()
            codigo_resultado = self.__snap7dll.Cli_ReadArea(
                self.__objetoS7, ClientePLCSiemens.__nombre_area[area], numero_db,
                direccion, num_registros, tipo_datos_area,
                datos
            )
            tiempo_lectura = (time.perf_counter() - hora_comienzo_lecturas)
            log.log(DEBUG_CLIENTE_PLC, '  -> datos=%s; codigo_resultado=%s; tiempo_lectura=%s',
                datos, codigo_resultado, tiempo_lectura
            )
            pausa_restante = self.pausa_entre_accesos - tiempo_lectura
            if pausa_restante > 0:
                time.sleep(pausa_restante)
        except Exception as e:
            # Se ha producido una excpeción, no un error de acceso, por lo que no hay
            # un código de error de la librería
            codigo_resultado = 0
            mensaje_resultado = 'ClientePLCSiemens.leer_area: {}: {}'.format(
                e.__class__.__name__, e
            )
        finally:
            if THREADSAFE:
                self.mutex_acceso.release()
        # Si se ha producido un error, generamos una excepción con el mensaje de error
        # que corresponde al código de error devuelto
        if codigo_resultado or mensaje_resultado:
            self.__generar_excepcion(codigo_resultado, mensaje_resultado)
        return datos


    def leer_registros(self, direccion: int, num_registros: int, numero_db: Optional[int]=None) -> bytes:
        ''' Lee bytes de un DB del PLC, a partir de la dirección indicada.
        @param direccion: Dirección del valor en el mapa del PLC.
        @param num_registros: Cantidad de registros (bytes) a leer.
        @param numero_db: número del DB del que leer. Es obligatorio indicarlo
            al menos en la primera lectura o escritura que se haga, en esta
            u otra función; en lecturas posteriores, si no se especifica,
            se usa el último valor pasado en llamadas anteriores.
        @return: Byte array con los valores leídos; se devuelven num_registros bytes.

        NOTA: Internamente llama al método "leer_area".
        '''
        # Usar en este método como número de DB el que se pasa como parámetro;
        # si no se pasa, copiar el que esté almacenado en la propiedad numero_db.
        # La propiedad numero_db puede cambiar si se produce una llamada a otro
        # método (una lectura por ejemplo) durante la ejecución de éste.
        if numero_db:
            self.numero_db = numero_db
        elif self.numero_db is not None:
            numero_db = self.numero_db
        else:
            raise PLCError('No se ha especificado el número del DB a leer')
        log.log(DEBUG_CLIENTE_PLC,
            '-> ClientePLCSiemens.leer_registros(%s,%s [%s])',
            direccion, num_registros, numero_db
        )
        return self.leer_area('db', direccion, num_registros, numero_db)


    def leer_valor(self, direccion: Union[int, float, str], tipo: Optional[TipoDatos]=None, numero_db: Optional[int]=None) -> Any:
        ''' Lee un valor individual de un cierto tipo en la dirección indicada,
            dentro de una BD del PLC.
        @param direccion: Dirección del valor en el mapa del PLC. Se puede usar un valor numérico (int o float)
            para indicar el offset dento del área por defecto del dispositivo; para leer un bit, se usa un
            número float con direccion.bit. En este caso es necesario pasar también el parámetro "tipo".
            Como alternativa, se puede pasar la dirección como una cadena de texto "area.tipo+direccion",
            en el formato aceptado por "mapear_variables".
        @param tipo: Valor TipoDatos del tipo de dato a leer. Necesario si "direccion" es un valor numérico;
            si "direccion" es de tipo "str", no se usa.
        @param numero_db: Número de la base de datos del PLC a leer. Es obligatorio indicarlo
            al menos en la primera lectura o escritura que se haga, si no viene en la misma dirección
            en forma de "dbN". En operaciones posteriores, si no se especifica, se usa el último valor
            pasado en llamadas anteriores.
        @return: Valor leido, en el tipo indicado.

        NOTA: Internamente llama al método "leer_area".
        '''
        ### ANULADA LLAMADA A ClientePLC, para mantener el número del DB con que se ha llamado
        # ClientePLC.escribir_valor(self, valor, direccion, tipo)

        (area, tipo, direccion, indice_bit) = self._obtener_direccion(direccion, tipo)
        ###TODO: Si se especifica "area", debería escribirse en el área correcta, no asumir DB o HR
        # Si incluye el nombre de un DB, intentar extraer el número del DB.
        if area.startswith('db'):
            try:
                numero_db = int(area[2:])
            except Exception as e:
                pass
        if numero_db:
            self.numero_db = numero_db
        elif self.numero_db is not None:
            numero_db = self.numero_db
        else:
            raise PLCError('No se ha especificado el número del DB a leer')
        log.log(DEBUG_CLIENTE_PLC,
            '-> ClientePLCSiemens.leer_valor(%s,%s,%s [%s])',
            direccion, tipo, numero_db, self.numero_db
        )
        num_registros = self._bytes_tipo_datos[tipo] // self.bytes_por_registro
        respuesta = self.leer_area('db', direccion, num_registros, numero_db)
        return self._bytes_a_valor(respuesta, tipo, indice_bit)


    def leer_array_valores(self, direccion: int, tipo: TipoDatos, numero_valores: int,
            numero_db: Optional[int]=None) -> List[Any]:
        ''' Lee un grupo consecutivo de valores del tipo indicado y a partir de la dirección
            indicada. Es más eficiente que leer varios valores individuales con la función
            leer_valor; la lectura de datos del PLC se hace en una sola llamada, y del resultado
            se extraen los valores solicitados.
        @param direccion: Dirección del primer valor en el mapa del PLC.
        @param tipo: Valor TipoDatos del tipo de los datos a leer
        @return: lista con los valores leidos, en el tipo indicado.

        NOTA: Internamente llama al método "leer_area".
        '''
        if numero_db:
            self.numero_db = numero_db
        elif self.numero_db is not None:
            numero_db = self.numero_db
        else:
            raise PLCError('No se ha especificado el número del DB a leer')
        ## Copiado de ClientePLC.leer_array_valores
        num_registros = numero_valores * self._bytes_tipo_datos[tipo] // self.bytes_por_registro
        respuesta = self.leer_area('db', direccion, num_registros, numero_db)
        array_valores_leidos = []
        for indice in range(numero_valores):
            indice_byte = indice * self._bytes_tipo_datos[tipo]
            indice_byte_siguiente = indice_byte + self._bytes_tipo_datos[tipo]
            array_valores_leidos.append(
                self._bytes_a_valor(respuesta[indice_byte:indice_byte_siguiente], tipo)
            )
        return array_valores_leidos


    def leer_lista_valores(self, lista_valores: Dict[Union[int, float], TipoDatos],
            numero_db: Optional[int]=None) -> Dict[int, Any]:
        ''' Lee una lista de valores, cada uno del tipo indicado y en la dirección indicada,
            dentro de un DB del PLC.
            Es más eficiente que leer varios valores individuales con la función leer_valor;
            la lectura de datos del PLC se hace en una sola llamada, y del resultado se
            extraen los valores solicitados.
        @param lista_valores: diccionario direccion:TipoDatos que describen las direcciones a
            leer y el tipo de dato de cada dirección.
        @param numero_db: Número de la base de datos del PLC a leer. Es obligatorio
            indicarlo al menos en la primera lectura que se haga, en esta u otra función
            de lectura de valores del PLC; en lecturas posteriores, si no se especifica,
            se usa el último valor pasado en llamadas anteriores.
        @return: diccionario direccion:valor con los valores leídos.

        NOTA: Internamente llama al método "leer_area".
        '''
        if numero_db:
            self.numero_db = numero_db
        elif self.numero_db is not None:
            numero_db = self.numero_db
        else:
            raise PLCError('No se ha especificado el número del DB a leer')
        log.log(DEBUG_CLIENTE_PLC,
            'ClientePLCSiemens.leer_lista_valores(%s [%s])', lista_valores, numero_db
        )
        # Para leer en una sola llamada todos los valores, calculamos el número de registros
        # que hay entre la direcciones más baja a leer y la más alta
        rangos = self._rango_posiciones(lista_valores)
        respuesta = {}
        for rango in rangos:
            registros = self.leer_area(
                'db', rango[self._DIRECCION_MIN], rango[self._NUM_REGISTROS], numero_db
            )
            respuesta.update(self._convertir_registros_a_valores(
                registros, rango[self._DIRECCION_MIN], rango[self._DIRECCION_MAX], lista_valores)
            )
        log.log(DEBUG_CLIENTE_PLC, '   %s', respuesta)
        return respuesta

    def escribir_area(self, valores: bytes, area: Union[int, str], direccion: int,
            num_registros: Optional[int]=1, id_adicional: Optional[int]=None) -> None:
        ''' Escribe en el PLC los valores en los registros a partir del indicado.
        @param area: Nombre del área de la que leer. Posibles valores:
            'pe': entradas de proceso
            'pa': salidas de proceso
            'mk': marcas
            'dbN': DB número N (N = entero positivo). Alternativa: usar solo 'db'
                e indicar el número del DB en el parámetro id_adicional.
            'ct': contadores
            'tm': timers
            Si "area" es numérico, se asume que el área es "DB" + número pasado.
        @param valores: byte array con los valores a escribir. La longitud de valores
            debe ser igual a num_registros * tamaño registro.
        @param direccion: Dirección del valor en el área del PLC. Si el área es 'mk',
            debe expresarse en bits.
        @param num_registros: Cantidad de registros a escribir.
        @param id_adicional: número del DB, si se lee del área "db". No hay que indicarlo
            si se especifica el número del DB en el nombre del área.
        '''
        # Si el área es numérica, se asume que es el DB con número indicado.
        if isinstance(area, int):
            numero_db = area
            area = 'db'
        else:
            area = area.lower()
            # Si el área empieza por "db", debe llevar a continuación el número del DB.
            if area.startswith('db'):
                try:
                    numero_db = int(area[2:])
                    area = 'db'
                except Exception as e:
                    if id_adicional is None:
                        raise PLCError('Número del DB no indicado en área ({}) ni en parámetro adicional ({}): {}'.format(area, id_adicional, e))
                    numero_db = id_adicional
            else:
                numero_db = 0

        log.log(DEBUG_CLIENTE_PLC, '-> ClientePLCSiemens.escribir_area(%s, %s, %s, %s)',
            area, valores, direccion, num_registros
        )
        tipo_datos_area = ClientePLCSiemens.__tipo_datos_area[area]
        num_bytes = ClientePLCSiemens.__longitud_tipo_s7[tipo_datos_area] * num_registros
        # Los valores deben venir en un array de bytes que se escribirá directamente
        if not isinstance(valores, bytes):
            raise PLCError('Los valores a escribir deben pasarse en un array de bytes')
        if len(valores) != num_bytes:
            raise PLCError('La longitud del array con los datos no se corresponde con el número de registros a escribir')
        mensaje_resultado = None
        try:
            if THREADSAFE:
                log.log(DEBUG_CLIENTE_PLC, '   mutex: %s [%s]', self.mutex_acceso, numero_db)
                if not self.mutex_acceso.acquire(timeout=self.timeout_acceso):
                    raise Exception('No se ha conseguido acceso exclusivo para escribir')
            if self.conectar_automaticamente and not self._conectado:
                self.conectar()
                time.sleep(self.pausa_entre_accesos)
            # Llamada a la función que escribe en el PLC:
            log.log(DEBUG_CLIENTE_PLC, '   Cli.WriteArea(objetoS7, %s, %s, %s, %s, %s, %s)',
                ClientePLCSiemens.__nombre_area[area], numero_db, direccion, num_registros,
                tipo_datos_area, valores
            )
            self.__snap7dll.Cli_WriteArea.argtypes = [
                CTYPES_HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, ctypes.c_char_p
            ]
            self.__snap7dll.Cli_WriteArea.restype = ctypes.c_int
            hora_comienzo_lecturas = time.perf_counter()
            codigo_resultado = self.__snap7dll.Cli_WriteArea(
                self.__objetoS7, ClientePLCSiemens.__nombre_area[area],
                numero_db, direccion, num_registros, tipo_datos_area,
                valores
            )
            tiempo_lectura = (time.perf_counter() - hora_comienzo_lecturas)
            log.log(DEBUG_CLIENTE_PLC,
                '  -> escrito area %s [%s], codigo_resultado=%s; tiempo_lectura=%s',
                area, numero_db, codigo_resultado, tiempo_lectura
            )
            pausa_restante = self.pausa_entre_accesos - tiempo_lectura
            if pausa_restante > 0:
                time.sleep(pausa_restante)
        except Exception as e:
            codigo_resultado = 0
            mensaje_resultado = 'ClientePLCSiemens.escribir_area: {}: {}'.format(
                e.__class__.__name__, e
            )
        finally:
            if THREADSAFE:
                self.mutex_acceso.release()
        # Si se ha producido un error, generamos una excepción con el mensaje de error
        # que corresponde al código de error devuelto
        if codigo_resultado or mensaje_resultado:
            self.__generar_excepcion(codigo_resultado, mensaje_resultado)


    def escribir_registros(self, valores: Union[int, bytes], direccion: int, num_registros: int,
            numero_db: Optional[int]=None) -> None:
        ''' Escribe en el PLC los valores en los registros a partir del indicado.
        @param valores: byte array con los valores a escribir. La longitud de valores
            debe ser igual a num_registros * tamaño registro.
            Si se pasa un valor entero, en lugar de un byte array, se escribe ese valor
            en el número de registros indicado.
        @param direccion: Dirección inicial en el mapa del PLC en que escribir
        @param num_registros: Cantidad de registros a escribir.
        @param numero_db: Número de la base de datos del PLC a escribir. Es obligatorio
            indicarlo al menos en la primera lectura o escritura que se haga, en esta
            u otra función; en lecturas posteriores, si no se especifica,
            se usa el último valor pasado en llamadas anteriores.
        '''
        # Usar en este método como número de DB el que se pasa como parámetro;
        # si no se pasa, copiar el que esté almacenado en la propiedad numero_db.
        # La propiedad numero_db puede cambiar si se produce una llamada a otro
        # método (una lectura por ejemplo) durante la ejecución de éste.
        if numero_db:
            self.numero_db = numero_db
        elif self.numero_db is not None:
            numero_db = self.numero_db
        else:
            raise PLCError('No se ha especificado el número del DB en que escribir')
        log.log(DEBUG_CLIENTE_PLC,
            '-> ClientePLCSiemens.escribir_registros(%s,%s,%s,%s [%s])',
            valores, direccion, num_registros, numero_db, self.numero_db
        )
        # Si se pasa como valor un número entero, se escribirá repetido en todas las direcciones
        if isinstance(valores, int):
            valores = bytes([valores] * (num_registros * self.bytes_por_registro))
        self.escribir_area(valores, 'db', direccion, num_registros, numero_db)


    def escribir_valor(self, valor: Any, direccion: Union[int, float, str], tipo: Optional[TipoDatos]=None,
            numero_db: Optional[int]=None) -> None:
        ''' Escribe en el PLC un valor del tipo indicado en la dirección indicada.
        @param valor: valor a escribir
        @param direccion: Dirección del valor en el mapa del PLC. Se puede usar un valor numérico (int o float)
            para indicar el offset dento del área por defecto del dispositivo; para escribir un bit, se usa un
            número float con direccion.bit. En este caso es necesario pasar también el parámetro "tipo".
            Como alternativa, se puede pasar la dirección como una cadena de texto "area.tipo+direccion",
            en el formato aceptado por "mapear_variables".
        @param tipo: Valor TipoDatos del tipo de dato a escribir. Necesario si "direccion" es un valor numérico;
            si "direccion" es de tipo "str", no se usa.
        @param numero_db: Número de la base de datos del PLC a escribir. Es obligatorio indicarlo
            al menos en la primera lectura o escritura que se haga, si no viene en la misma dirección
            en forma de "dbN". En operaciones posteriores, si no se especifica, se usa el último valor
            pasado en llamadas anteriores.
        NOTA: Internamente llama a "escribir_area".
        '''
        ### ANULADA LLAMADA A ClientePLC, para mantener el número del DB con que se ha llamado
        # if numero_db:
        #     self.numero_db = numero_db
        # elif self.numero_db is None:
        #     raise PLCError('No se ha especificado el número del DB en que escribir')
        # log.log(DEBUG_CLIENTE_PLC,
        #    '-> ClientePLCSiemens.escribir_valor(%s,%s,%s,%s [%s])',
        #    valor, direccion, tipo, numero_db, self.numero_db)
        # ClientePLC.escribir_valor(self, valor, direccion, tipo)

        (area, tipo, direccion, indice_bit) = self._obtener_direccion(direccion, tipo)
        ###TODO: Si se especifica "area", debería escribirse en el área correcta, no asumir DB o HR
        # Si incluye el nombre de un DB, intentar extraer el número del DB.
        if area.startswith('db'):
            try:
                numero_db = int(area[2:])
            except Exception as e:
                pass
        # Usar en este método como número de DB el que se pasa como parámetro;
        # si no se pasa, copiar el que esté almacenado en la propiedad numero_db.
        # La propiedad numero_db puede cambiar si se produce una llamada a otro
        # método (una lectura por ejemplo) durante la ejecución de éste.
        if numero_db:
            self.numero_db = numero_db
        elif self.numero_db is not None:
            numero_db = self.numero_db
        else:
            raise PLCError('No se ha especificado el número del DB en que escribir')
        log.log(DEBUG_CLIENTE_PLC,
            '-> ClientePLCSiemens.escribir_valor(%s,%s,%s [%s])', valor, direccion, tipo, numero_db
        )
        datos = self._valor_a_bytes(valor, tipo, indice_bit)
        if tipo == TipoDatos.booleano:
            # Leer el valor del registro completo que contiene el bit, para
            # combinarlo con el bit a escribir y así no modificar los valores
            # del resto de bits
            registro_actual = self.leer_area('db', direccion, 1, numero_db)
            # Las operaciones bitwise no se pueden aplicar a byte arrays (son inmutables);
            # convertimos los valores a entero (lo que permite usar todos los bits del registro,
            # sea de 8 o 16 bits), los combinamos, y luego convertirlo de vuelta a byte array
            bits = int.from_bytes(registro_actual, byteorder='big')
            bits_escribir = int.from_bytes(datos, byteorder='big')
            bits_resultado = (bits & ~(1 << indice_bit)) | bits_escribir
            datos = bits_resultado.to_bytes(self.bytes_por_registro, byteorder='big', signed=False)
        num_registros = self._bytes_tipo_datos[tipo] // self.bytes_por_registro
        self.escribir_area(datos, 'db', direccion, num_registros, numero_db)


    def leer_marca(self, direccion: float) -> bool:
        ''' Lee el valor de una marca individual, en la dirección indicada.
        @param direccion: Dirección de la marca, en formato direccion.bit
        @return Valor de la marca: True o False
        NOTA: Internamente llama al método "leer_area"
        '''
        log.log(DEBUG_CLIENTE_PLC, '-> ClientePLCSiemens.leer_marca(%s)', direccion)
        # Para leer marcas, usamos una función directa de la librería Snap7

        # Al leer bits, la función Cli_ReadArea espera la dirección en bits
        # (numero registro * 8 + indice bit).
        (direccion_registro, indice_bit) = self._separar_direccion_bit(direccion)
        direccion = direccion_registro * 8 + indice_bit
        datos = self.leer_area('mk', direccion, 1)
        return datos[0] != 0


    def escribir_marca(self, valor: bool, direccion: float) -> None:
        ''' Escribe una marca individual.
        @param valor: Valor a escribir, True o False
        @param direccion: Dirección de la marca, en formato direccion.bit
        NOTA: Internamente llama al método "escribir_area"
        '''
        ###TODO: NO FUNCIONA (o escribr o leer, o ambos), REVISARLO
        log.log(DEBUG_CLIENTE_PLC, '-> ClientePLCSiemens.escribir_marca(%s, %s)', valor, direccion)
        # Para escribir una marca, hay que hacerlo con una llamada a una función directa de Snap7
        # Al escribir bits, la función Cli_WriteArea espera la dirección en bits
        # (numero registro * 8 + indice bit).
        (direccion_registro, indice_bit) = self._separar_direccion_bit(direccion)
        direccion = direccion_registro * 8 + indice_bit
        valor_bytes = self._valor_a_bytes(valor, TipoDatos.booleano)
        self.escribir_area(valor_bytes, 'mk', direccion, num_registros=1)


#############################################################################

class ClientePLCModbus(ClientePLC):
    ''' Objeto cliente para comunicación con dispositivos (no solo PLCs) a
    través de Modbus TCP.
    Versión "thread safe": las lecturas y escrituras al dispositivoPLC usan un
    mutex que evita que se solapen y causen "race conditions".
    '''

    # Números de función Modbus
    READ_COILS = 1
    READ_DISCRETE_INPUTS = 2
    READ_HOLDING_REGISTERS = 3
    READ_INPUT_REGISTERS = 4
    WRITE_SINGLE_COIL = 5
    WRITE_SINGLE_REGISTER = 6
    WRITE_MULTIPLE_COILS = 15
    WRITE_MULTIPLE_REGISTERS = 16

    __numeros_funcion_modbus = (
        READ_COILS,
        READ_DISCRETE_INPUTS,
        READ_HOLDING_REGISTERS,
        READ_INPUT_REGISTERS,
        WRITE_SINGLE_COIL,
        WRITE_SINGLE_REGISTER,
        WRITE_MULTIPLE_COILS,
        WRITE_MULTIPLE_REGISTERS
    )
    __nombre_area_lectura = {
        'co': READ_COILS,
        'in': READ_DISCRETE_INPUTS,
        'hr': READ_HOLDING_REGISTERS,
        'ir': READ_INPUT_REGISTERS
    }
    __nombre_area_escritura = {
        'co': WRITE_SINGLE_COIL,
        'hr': WRITE_SINGLE_REGISTER
    }
    __nombre_area_escritura_multiple = {
        'co': WRITE_MULTIPLE_COILS,
        'hr': WRITE_MULTIPLE_REGISTERS
    }
    # Códigos estándar de error devuelto
    __codigos_excepcion = {
        1: 'Función no válida',
        2: 'Dirección de registro no válida',
        3: 'Valor de dato no válido',
        4: 'Fallo del dispositivo'}

    def __init__(self, ip: Optional[str]=None, puerto: Optional[int]=None, direccion_dispositivo: Optional[int]=None,
            invertir_palabras: Optional[bool]=True, invertir_bytes: Optional[bool]=False) -> None:
        ''' Constructor. Crea el objeto para comunicar con el dispositivo, pero no
        intenta conectar con él.
        @param ip (str): dirección IPv4 del dispositivo
        @param puerto (int, opcional): puerto TCP del dispositivo; por defecto, 502
        @param direccion_dispositivo (int, opcional): dirección Modbus del dispositivo.
            Por defecto es 0 = broadcast; hay dispositivos que no responden
            si no se especifica su dirección exacta (entre 1 y 247).
        @param invertir_palabras (bool, opcional): Si True, el dispositivo
            devuelve los valores de 32 bits con la palabra menos significativa primero,
            aunque los bytes dentro de cada palabra siempre están con el byte
            más siginificativo primero, por lo que hay que invertir las palabras
            para obtener el valor correcto: AB CD se almacena como CD AB, AB   CDEFGH
            como GH EF CD AB.
            Aparentemente, casi todos los dispositivos Modbus usan este protocolo,
            por lo que por defecto es True.
        @param invertir_bytes (bool, opcional): Si True, el dispositivo almacena
            los valores de 32 bits con los bytes invertidos en cada palabra:
            AB CD se almacena como BA DC, AB CD EF GH como BA DC FE HG.
            No es frecuente, por lo que por defecto es False.
            Si invertir_palabras e invertir_bytes son ambos True, AB CD se almacena DC BA,
            AB CD EF GH como HG FE DC BA.
        '''
        if puerto is None:
            puerto = 502
        if direccion_dispositivo is None:
            direccion_dispositivo = 0
        super().__init__(ip, puerto)
        # Los registros ModBus son de 2 bytes
        self.bytes_por_registro = 2
        # Por tanto, hay que redefinir los tamaños de los tipos
        # que en la clase base son de 1 byte...
        self._bytes_tipo_datos[TipoDatos.booleano] = 2
        self._bytes_tipo_datos[TipoDatos.byte] = 2
        #... y los caracteres de formato correspondientes
        self._cadena_formato_tipo_datos[TipoDatos.booleano] = 'H'
        self._cadena_formato_tipo_datos[TipoDatos.byte] = 'H'
        # El límite de registros por petición está limitado:
        self.max_registros_por_lectura = 123
        # Modbus por defecto usa formato big endian.
        self.orden_bytes = '>'
        # Indicador de que los valores de 32 y 64 bits se almacenan con la palabra
        # menos significativa primero, por lo que hay que invertir las palabras
        # al hacer la conversión a tipo de datos Python.
        self.invertir_palabras = invertir_palabras
        # Indicador de que los valores de 32 y 64 bits se almacenan con los bytes
        # invertidos en cada palabra, por lo que hay que invertirlos al hacer la
        # conversión a tipo de datos Python.
        self.invertir_bytes = invertir_bytes

        # Socket para comunicación TCP con el dispositivo
        self.__socket = None

        # Identificador del esclavo Modbus a leer; por defecto 0
        self.id_esclavo = direccion_dispositivo


    def __cabecera_mbap(self, id_esclavo: int, longitud_pdu: int) -> bytes:
        ''' Devuelve un byte array con la cabecera del mensaje Modbus TCP.

        @param id_esclavo (byte): Número de esclavo; 0 = broadcast.
        @param longitud_pdu: Número de bytes del PDU (para calcular longitud total mensaje).
        @return: Byte array de 7 bytes con la cabecera MBAP.
        '''
        # Como identificador de transacción, generamos un número entero aleatorio
        # de 16 bits (2^16 = 65536). Ojo: el número no puede ser 65536, ya serían 17 bit
        id_transaccion = randint(0, 65535)

        return struct.pack('>HHHB', id_transaccion, 0, longitud_pdu + 1, id_esclavo)

    def __mensaje_error(self, codigo_error: int) -> str:
        mensaje = 'Error modbus {}'.format(codigo_error)
        if codigo_error in ClientePLCModbus.__codigos_excepcion:
            mensaje += ': ' + ClientePLCModbus.__codigos_excepcion[codigo_error]
        return mensaje


    def conectar(self, ip: Optional[str]=None, direccion_dispositivo: Optional[int]=None) -> None:
        '''
        @param ip (str, opcional): si se pasa la IP aquí, se usará para conectar con el autómata.
            Si no, se usa la IP usada en el constructor. Si no se ha especificado ni aquí ni en
            el constructor, se generará una excepción ValueError.
        @param direccion_dispositivo (opcional): dirección Modbus del dispositivo.
            Si se pasa aquí, se usará para conectar con el autómata; si no, se usa la dirección
            indicada en el constructor.
        '''
        # Si ya está conectado: si es al mismo autómata (misma ip y dirección),
        # y responde a un ping, no hacer nada.
        # Si no, desconectar antes de conectar al nuevo autómata.
        if self._conectado:
            if (ip is None or self.ip == ip) and \
                (direccion_dispositivo is None or self.id_esclavo == direccion_dispositivo):
                # Si se ha pedido conectar a la misma ip y dirección, hacer un ping
                # para comprobar si la conexión sigue activa; si es así, no hacer nada.
                if ping2(self.ip, intentos=3):
                    return
            self.desconectar()
        if ip is not None:
            self.ip = ip
        if direccion_dispositivo is not None:
            self.id_esclavo = direccion_dispositivo

        # Comprobar la IP, generando excepción ValueError si no es válida
        ipaddress.ip_address(self.ip)

        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.settimeout(3)
        try:
            # Abrimos la conexión (socket).
            # El método .connect espera un solo parámetro, por lo que se la pasa IP
            # y puerto como una tupla
            self.__socket.connect((self.ip, self.puerto))
            self._conectado = True
            log.info(
                'Conectado al dispositivo Modbus: IP=%s, puerto=%s, direccion=%s',
                self.ip, self.puerto, self.id_esclavo
            )

        except ConnectionRefusedError:
            try:
                self.__socket.close()
            except Exception:
                pass
            self.__socket = None
            raise PLCErrorComunicacion(
                'ERROR: No se puede conectar con el dispositivo: IP={}, puerto={}, direccion={}'.format(
                    self.ip, self.puerto, self.id_esclavo
                )
            )
        except TimeoutError:
            try:
                self.__socket.close()
            except Exception:
                pass
            self.__socket = None
            raise PLCErrorComunicacion(
                'ERROR: El dispositivo no responde: IP={}, puerto={}, direccion={}'.format(
                    self.ip, self.puerto, self.id_esclavo
                )
            )
        except Exception as e:
            try:
                self.__socket.close()
            except Exception:
                pass
            self.__socket = None
            raise PLCErrorComunicacion(
                'ERROR al conectar con el dispositivo: IP={}, puerto={}, direccion={}: {}'.format(
                    self.ip, self.puerto, self.id_esclavo, e
                )
            )


    def desconectar(self) -> None:
        if self.__socket:
            self.__socket.close()
            self.__socket = None
            self._conectado = False
            log.info(
                'Desconectado del dispositivo Modbus: IP=%s, puerto=%s, direccion=%s',
                self.ip, self.puerto, self.id_esclavo
            )

    def leer_area(self, area: str, direccion: int, num_registros: int, id_adicional: Optional[int]=None) -> bytes:
        ''' Lee bytes de una de las áreas del dispositivo, a partir de la
        dirección indicada.
        @param area: Nombre del área de la que leer:
            'co' = "Coils", entradas/salidas digitales
            'in' = "Discrete Inputs", entradas digitales
            'hr' = "Holding Registers", registros de entrada/salida
            'ir' = "Input Registers", registros de entrada (entradas analógicas)
            Si "area" es None, se asume 'hr'.
            Se puede indicar un número a continuación del nombre del área; si se
            especifica, se usa como identificador de dispositivo esclavo Modbus.
            Esto permite acceder a dispositivos que tiene varios "subdipositivos",
            a los que se accede por distintos números de dispositivo Modbus.
            Si no se especifica, se usa "id_adicional" como número de dispositivo
            Modbus; y si éste tampoco se especifica, se usa el número de dispositivo
            anterior, o el definido en el constructor.
        @param direccion: Dirección del valor en el mapa del dispositivo.
        @param num_registros: Cantidad de registros a leer.
        @param id_adicional: Identificador del esclavo Modbus del que leer.
            Si se especifica, se usa a partir de esta llamada como el id a usar
            por defecto, hasta que se pase un valor distinto.
        @return: Byte array con los valores leídos; se devuelven num_registros
            bytes.

        NOTA: El máximo número de registros que se pueden leer simultáneamente
        es 123. Según el estándar Modbus:
        "The quantity of registers to be read, combined with all the other
        fileds in the expected response, must not exceed the allowable length
        of Modbus messages: 256 bytes."
        Al usar Modbus/TCP, la cabecera tiene 7 bytes; mas otros dos bytes
        para el número de función y el número de bytes devueltos, deja 247
        bytes para datos, que dividido entre 2, son 123 words.

        NOTA: Hay servidores Modbus que dan error si se intenta leer un número
        de registro que no tienen definido; en estos casos, hay que separar la
        lectura en tramos de registros contiguos que sí sean accesibles.
        '''
        ###TODO: No funciona tipo datos booleano, ¿real, entero largo ni real largo?
        log.log(
            DEBUG_CLIENTE_PLC,
            '-> ClientePLCModbus.leer_area(%s,%s,%s,%s)',
            area, direccion, num_registros, id_adicional
        )
        if None in [direccion, num_registros]:
            raise PLCErrorModbus(3)
        if num_registros > 123:
            raise PLCErrorModbus(3)
        if area is None:
            area = 'hr'
        elif not area[0:2] in ClientePLCModbus.__nombre_area_lectura:
            raise PLCErrorModbus(3)
        try:
            num_dispositivo_area = int(area[2:])
        except ValueError:
            num_dispositivo_area = None
        area = area[0:2]

        try:
            if THREADSAFE:
                self.mutex_acceso.acquire()
            if self.conectar_automaticamente and not self._conectado:
                self.conectar()
                time.sleep(self.pausa_entre_accesos)
            try:
                if id_adicional is not None:
                    self.id_esclavo = id_adicional
                pdu = struct.pack(
                    '>BHH', ClientePLCModbus.__nombre_area_lectura[area],
                    direccion, num_registros
                )
                ###log.log(DEBUG_CLIENTE_PLC, '   pdu = %s', pdu)
                adu = self.__cabecera_mbap(
                    num_dispositivo_area if num_dispositivo_area else self.id_esclavo,
                    len(pdu)
                ) + pdu
                ###log.log(DEBUG_CLIENTE_PLC, '   adu = %s', adu)
            except Exception as e:
                log.error(
                    'ClientePLCModbus.leer_area(%s,%s,%s,%s): %s',
                    area, direccion, num_registros, id_adicional, e
                )
                # Si no se puede construir el PDU o el ADU, devolver error en
                # los datos pasados a la función
                raise PLCErrorModbus(3, str(e))
            try:
                self.__socket.send(adu)
                datos = self.__socket.recv(512)
                log.log(DEBUG_CLIENTE_PLC, '   -> datos = %s; len = %s', datos, len(datos))
                # Si no se reciben al menos los bytes solicitados, dar error de comunicación
                if len(datos) < (num_registros - 1) * self.bytes_por_registro + len(adu) - 1:
                    raise PLCErrorComunicacion('Se han recibido menos bytes que los solicitados')
            except Exception as e:
                if self.__socket is None:
                    mensaje = 'El dispositivo está desconectado'
                else:
                    mensaje = str(e)
                # Interpretamos cualquier error como de comunicación, ya que se
                # deberá a la llamada a "socket.send"
                if self.desconectar_si_error_comunicacion:
                    try:
                        self.desconectar()
                        time.sleep(self.pausa_entre_accesos)
                    except Exception:
                        pass
                raise PLCErrorComunicacion(mensaje)

            # Extraemos el código de función devuelto; si no es un código de función Modbus,
            # es que se ha producido un error. Si es así, generamos una excepción con el
            # código de error.
            # El [0] es porque unpack devuelve una tupla, aunque se pida un solo valor
            codigo_funcion = struct.unpack('>B', datos[7:8])[0]
            if codigo_funcion not in ClientePLCModbus.__numeros_funcion_modbus:
                codigo_error = struct.unpack('>B', datos[8:9])[0]
                raise PLCErrorModbus(self.__mensaje_error(codigo_error))
            # Quitamos cabecera (7 bytes), id funcion (1 byte) y num.registros (1 byte)
            respuesta = datos[9:]
            log.log(DEBUG_CLIENTE_PLC, '   %s', respuesta)
            return respuesta
        finally:
            if THREADSAFE:
                self.mutex_acceso.release()


    def leer_registros(self, direccion: int, num_registros: int, id_adicional: Optional[int]=None) -> bytes:
        ''' Función Modbus 3: Read holding registers.
            Equivale a la función leer_area con area = 'hr', "Holding
            Registers".
        '''
        log.log(
            DEBUG_CLIENTE_PLC,
            '-> ClientePLCModbus.leer_registros(%s,%s,%s)',
            direccion, num_registros, id_adicional
        )
        return self.leer_area('hr', direccion, num_registros, id_adicional)


    def escribir_registros(self, valores: bytes, direccion: int, num_registros: int,
            id_adicional: Optional[int]=None) -> None:
        ''' Función Modbus 16: Write multiple registers.
        Comenzando por el registro "dirección", escribe en el dispositivo "valores".
        @param valores: byte array con los valores a escribir. La longitud de valores
            debe ser igual a num_registros * tamaño registro.
        @param direccion: Dirección inicial (offset) en el mapa del dispositivo en que escribir.
            Primer registro = 0.
        @param num_registros: Cantidad de registros a escribir.
        @param id_adicional: Identificador del esclavo Modbus del que leer.
            Si se especifica, se usa a partir de esta llamada como el id a usar
            por defecto, hasta que se pase un valor distinto. Inicialmente vale 0.
        '''
        log.log(
            DEBUG_CLIENTE_PLC,
            '-> ClientePLCModbus.escribir_registros(%s, %s, %s, %s)',
            valores, direccion, num_registros, id_adicional
        )
        if None in [valores, direccion, num_registros]:
            raise PLCErrorModbus(3)
        if num_registros > 123:
            raise PLCErrorModbus(3)

        try:
            if THREADSAFE:
                self.mutex_acceso.acquire()
            if self.conectar_automaticamente and not self._conectado:
                self.conectar()
                time.sleep(self.pausa_entre_accesos)
            if id_adicional is not None:
                self.id_esclavo = id_adicional

            num_bytes = num_registros * self.bytes_por_registro
            pdu = struct.pack(
                '>BHHB', ClientePLCModbus.WRITE_MULTIPLE_REGISTERS,
                direccion, num_registros, num_bytes
            )
            for valor in valores:
                pdu += struct.pack('>B' if valor >= 0 else '>b', valor)
            adu = self.__cabecera_mbap(self.id_esclavo, len(pdu)) + pdu

            try:
                bytes_enviados = self.__socket.send(adu)
                if bytes_enviados < len(adu):
                    raise Exception('No se han enviado todos los bytes al dispositivo')
                datos = self.__socket.recv(1024)
            except Exception as e:
                if self.__socket is None:
                    mensaje = 'El dispositivo está desconectado'
                else:
                    mensaje = str(e)
                # Interpretamos cualquier error como de comunicación, ya que se
                # deberá a la llamada a "socket.send"
                if self.desconectar_si_error_comunicacion:
                    try:
                        self.desconectar()
                        time.sleep(self.pausa_entre_accesos)
                    except Exception:
                        pass
                raise PLCErrorComunicacion(mensaje)
            # Extraemos el código de la función, para comprobar si se ha devuelto un error.
            # Si es así, generamos una excepción con el código de error.
            # El [0] es porque unpack devuelve una tupla, aunque se pida un solo valor
            codigo_funcion = struct.unpack('>B', datos[7:8])[0]
            if codigo_funcion not in ClientePLCModbus.__numeros_funcion_modbus:
                codigo_error = struct.unpack('>B', datos[8:9])[0]
                raise PLCErrorModbus(self.__mensaje_error(codigo_error))
            log.log(DEBUG_CLIENTE_PLC, '   escrito')
        finally:
            if THREADSAFE:
                self.mutex_acceso.release()

#############################################################################

class ClientePLCOpcUa(ClientePLC):
    ''' 
    Objeto cliente para comunicación con dispositivos (no solo PLCs) a 
    través de OCP-UA.
    Versión Síncrona Beta.
    '''
    def __init__(self, url: Optional[str], timeout: Optional[int]=4) -> None:
        '''
        Constructor. Crea el objeto para comunicar con el dispositivo, pero no 
        intenta conectar con él.
        @param url (str): dirección url del servidor. La url puede ser en formato
            UA-TCP o HTTPS.
            Si no se especifica su url aquí, se necesitará como parámetro en el método
            conectar().
        @param timeout (int): Cada petición enviada espera una respuesta en ese 
            tiempo. El timeout se especifica en segundos.
        '''
        super().__init__(url)
        self.timeout_acceso = timeout
    

    def conectar(self, url: Optional[str] = None) -> None:
        '''
        Método para conectar un cliente a un servidor.
        @param url (str): dirección url del servidor. La url puede ser en formato
            UA-TCP o HTTPS.
            Si no se especifica su url aquí, se debe especificar como parámetro en el
            constructor.
        '''
        if self._conectado:
            if(url is None or self.ip == url):
                # Si se ha pedido conectar a la misma ip y dirección, hacer un ping
                # para comprobar si la conexión sigue activa; si es así, no hacer nada.
                # if ping2(self.ip, intentos=3):
                #     return 
                pass
            self.desconectar()
        if url is not None:
            self.ip = url
        
        # Establecemos conexion creando un nuevo ojeto
        try:
            self.cliente = Client(url=self.ip,timeout=self.timeout_acceso)
            self.cliente.connect()
            self._conectado = True
            log.info(
                'Conectado al servidor a través de OPC-UA: URL=%s, Timeout=%s',
                self.ip, self.timeout_acceso
            )
        except Exception:
            raise PLCErrorComunicacion(
                'ERROR: No se pudo conectar con el dispositivo por OPC-UA: URL=%s, Timeout=%s',
                self.ip, self.timeout_acceso
            )
    

    def desconectar(self) -> None:
        if hasattr(self, "cliente"):
            self.cliente.disconnect()
            log.info(
                    'Desconectado el dispositivo OPC-UA: URL=%s, Timeout=%s',
                    self.ip, self.timeout_acceso
                )


    def leer_valor(self, indice: int=0, id: str=None) -> Any:
        '''
        Lee un valor aislado de una dirección dada.
        @param nameSpaceIndex (int): Índice del espacio de nombres donde se encuentra el valor que
            se desea leer.
            Si no se especifica el índice por defecto es 0.
        @param identificador (Union[str,int]): Indentificador del nodo que se desea leer.
        @return (Any): Devuelve un valor de cualquier tipo.
        '''
        if (id is None): 
            raise PLCErrorOpcUa(mensaje_error='No se ha especificado el identificador del nodo a leer')
        try:
            return self.cliente.get_node('ns='+str(indice)+';s='+id).read_value()
        except ua.uaerrors.UaStatusCodeError as e:
            raise PLCErrorOpcUa(e.code, e.__str__()) from e
        except ua.UaError as e:
            raise PLCErrorOpcUa(mensaje_error=e.__str__()) from e
        except Exception as e:
            raise PLCError('No se ha podido acceder al nodo especificado') from e

    # Añadir comprobaciones
    def mapear_variables(self, variables: Dict[str, str]) -> Dict[str, Any]:
        '''
        Devuelve un array de nodos especificados en los parámtros.
        @param variables: diccionario {nombre_variable, identificador_opc_ua}
        '''
        log.log(DEBUG_CLIENTE_PLC, '-> ClientePLC.mapear_variables(%s)', variables)
        resultado_nodos = dict()
        try:
            for nombre_variable, identificador_opc_ua in variables.items():
                identificadores = identificador_opc_ua.split(';')
                resultado_nodos[nombre_variable] = (ua.NodeId(identificadores[1], int(identificadores[0]) , ua.NodeIdType.String))
        except Exception as e:
            pass
        return resultado_nodos    

    def leer_mapa_variables(self, mapa_variables: Dict[str, Any]) -> Dict[str,Any]:
        nodos = []
        for nombre_variables in mapa_variables:
            nodos.append(mapa_variables[nombre_variables])
        valores = self.cliente.read_values(nodos)
        cont = 0
        for nombre_variables in mapa_variables:
            mapa_variables[nombre_variables] = valores[cont]
            cont += 1
        return mapa_variables


    def escribir_valor(self) -> None:pass