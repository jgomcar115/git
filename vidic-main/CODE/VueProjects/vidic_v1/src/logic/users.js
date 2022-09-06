// src/logic/users.js
import axios from "axios";

// BaseURL de axios está definida en /src/axios.js

export default {
    getUsuario() {  // Accede a BaseURL/usuario
        return axios.get('usuario');
        // return {'nombre_usuario': 'albertoUsuario', 'nombre':'Alberto'}     //simulacion offline 
    },
    postToken(nombre_usuario, contrasenya) {
    // postToken() {
        try{
            return axios.post('token?nombre_usuario=' + nombre_usuario + '&contrasenya=' + contrasenya)
            // return {'nombre_usuario': 'albertoUsuario', 'nombre':'Alberto'}     //simulacion offline 
        
        } catch (error) {
            console.log(error)
            return null
        }
    }
}