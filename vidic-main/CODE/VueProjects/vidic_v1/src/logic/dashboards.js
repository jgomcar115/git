// src/logic/dashboards.s
import axios from "axios";

// BaseURL de axios está definida en /src/axios.js

export default {
    getDashboards(nombre_usuario) {
    // getDashboards() { //simulacion offline
        return axios.get('dashboards?nombre_usuario=' + nombre_usuario);
        // return {'dashboards': ['instalacion_1', 'instalacion_2']}  // simulación offline
    },
    // getNumeroDashboards(nombre_usuario) {  //no hace falta si tienes la longitud de los dashboards
    //     return axios.get('numero-dashboards?nombre_usuario=' + nombre_usuario)
    //     // return nombre_usuario === nombre_usuario
    // },
    getDispositivo(id_dispositivo, fecha_inicio, fecha_fin) {
        return axios.get('dispositivo?id_dispositivo=' + id_dispositivo + '&fecha_inicio=' + fecha_inicio + '&fecha_fin=' + fecha_fin)
    }
}